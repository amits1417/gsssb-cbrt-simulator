import os
import sys
import json
import hashlib
import io
import time
import re
import pdfplumber
from PIL import Image

def get_icon_correctness(img_obj):
    try:
        stream_data = img_obj['stream'].get_data()
        h = hashlib.md5(stream_data).hexdigest()
        
        # Hardcoded hashes for GSSSB standard icons (super fast)
        if h == "ea13bea0000436f14d3cd78a87a479f9":
            return True
        if h == "bfdc06ca4544a342da65f9966840dc03":
            return False
            
        # Fallback: Color analysis using Pillow
        from PIL import Image
        img = Image.open(io.BytesIO(stream_data))
        img = img.convert('RGB')
        
        green_pixels = 0
        red_pixels = 0
        for x in range(img.width):
            for y in range(img.height):
                r, g, b = img.getpixel((x, y))
                # Detect green vs red pixels
                if g > r + 20 and g > b + 20:
                    green_pixels += 1
                elif r > g + 20 and r > b + 20:
                    red_pixels += 1
                    
        return green_pixels > red_pixels
    except Exception as e:
        return False

def parse_pdf(pdf_path, output_dir):
    print(f"Opening PDF: {pdf_path}")
    
    exam_id = os.path.splitext(os.path.basename(pdf_path))[0]
    exam_assets_dir = os.path.join(output_dir, "exams", exam_id)
    if not os.path.exists(exam_assets_dir):
        os.makedirs(exam_assets_dir)
        
    raw_blocks = []
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"Total pages: {total_pages}")
        
        current_block = None
        
        for p_idx, page in enumerate(pdf.pages):
            # Extract layout elements
            words = page.extract_words()
            images = page.images
            
            # Combine elements with coordinates and sort them top to bottom
            elements = []
            
            # Reconstruct lines
            lines_dict = {}
            for w in words:
                top_key = round(w['top'], 1)
                if top_key not in lines_dict:
                    lines_dict[top_key] = []
                lines_dict[top_key].append(w)
                
            sorted_line_tops = sorted(lines_dict.keys())
            
            for top in sorted_line_tops:
                line_words = sorted(lines_dict[top], key=lambda x: x['x0'])
                line_text = " ".join([w['text'] for w in line_words])
                x0 = line_words[0]['x0']
                x1 = line_words[-1]['x1']
                bottom = max(w['bottom'] for w in line_words)
                
                elements.append({
                    'type': 'text_line',
                    'text': line_text,
                    'x0': x0,
                    'top': top,
                    'x1': x1,
                    'bottom': bottom
                })
                
            for img in images:
                elements.append({
                    'type': 'image',
                    'x0': img['x0'],
                    'top': img['top'],
                    'x1': img['x1'],
                    'bottom': img['bottom'],
                    'width': img['width'],
                    'height': img['height'],
                    'raw_object': img
                })
                
            # Sort all page elements by top position
            elements.sort(key=lambda e: e['top'])
            
            # Pre-scan for the first Question Number header on this page
            first_header_el = None
            first_page_block = None
            for el in elements:
                if el['type'] == 'text_line' and "Question Number :" in el['text']:
                    first_header_el = el
                    break
                    
            if first_header_el is not None:
                # We have a header on this page. Pre-create its block so top elements are appended to it
                parts = first_header_el['text'].split()
                q_num = None
                q_id = None
                try:
                    q_num_idx = parts.index("Number") + 2
                    q_num = int(parts[q_num_idx].replace(":", ""))
                except ValueError:
                    pass
                try:
                    q_id_idx = parts.index("Id") + 2
                    q_id = parts[q_id_idx].replace(":", "")
                except ValueError:
                    pass
                    
                if q_num is not None:
                    # Create the first block for this page
                    first_page_block = {
                        'number': q_num,
                        'id': q_id,
                        'english_prompt': "",
                        'gujarati_prompt_box': None,
                        'options': [],
                        'temp_options_icons': []
                    }
                    raw_blocks.append(first_page_block)
            
            for el in elements:
                # 1. Detect New Question Header
                if el['type'] == 'text_line' and "Question Number :" in el['text']:
                    parts = el['text'].split()
                    q_num = None
                    q_id = None
                    try:
                        q_num_idx = parts.index("Number") + 2
                        q_num = int(parts[q_num_idx].replace(":", ""))
                    except ValueError:
                        pass
                        
                    try:
                        q_id_idx = parts.index("Id") + 2
                        q_id = parts[q_id_idx].replace(":", "")
                    except ValueError:
                        pass
                        
                    if q_num is not None:
                        # If this is the FIRST header on the page, we already pre-created its block!
                        if first_header_el is not None and el['top'] == first_header_el['top']:
                            current_block = first_page_block
                            continue
                            
                        # Create a new raw block
                        current_block = {
                            'number': q_num,
                            'id': q_id,
                            'english_prompt': "",
                            'gujarati_prompt_box': None, # (page_idx, box)
                            'options': [], # [{ 'box': ..., 'top': top, 'is_correct': bool }]
                            'temp_options_icons': []
                        }
                        raw_blocks.append(current_block)
                            
                elif current_block is not None:
                    # 2. Add elements to the current active block
                    if el['type'] == 'text_line':
                        text = el['text']
                        if any(sys_t in text for sys_t in ["Question Number :", "Mandatory or Optional :", "Options :", "Correct Marks :", "Wrong Marks :"]):
                            continue
                        
                        # Parse option line e.g. "1. Text"
                        match = re.match(r"^([1-4])\.\s*(.+)$", text.strip())
                        if match:
                            opt_idx = int(match.group(1))
                            opt_text = match.group(2)
                            
                            # Switch to first header block if current block is already full (has 4 options)
                            if len(current_block['options']) >= 4 and first_page_block is not None and current_block != first_page_block:
                                current_block = first_page_block
                                
                            current_block['options'].append({
                                'text': opt_text,
                                'index': opt_idx,
                                'is_correct': False,
                                'top': el['top'],
                                'bottom': el['bottom']
                            })
                            continue
                            
                        # If it is just a prefix on a line, skip
                        if text.strip() in ["1.", "2.", "3.", "4."]:
                            continue
                        
                        if text not in current_block['english_prompt']:
                            if current_block['english_prompt']:
                                current_block['english_prompt'] += "\n" + text
                            else:
                                current_block['english_prompt'] = text
                                
                    elif el['type'] == 'image':
                        x0 = el['x0']
                        w = el['width']
                        
                        # Classification based on horizontal position (x0)
                        if 40 <= x0 < 55 and w <= 18:
                            # Option check/cross icon
                            if len(current_block['temp_options_icons']) >= 4 and first_page_block is not None and current_block != first_page_block:
                                current_block = first_page_block
                                
                            is_correct = get_icon_correctness(el['raw_object'])
                            current_block['temp_options_icons'].append({
                                'top': el['top'],
                                'bottom': el['bottom'],
                                'is_correct': is_correct
                            })
                        else:
                            # Prompt or Option image
                            if x0 < 40:
                                # Starts at left margin. If width is small (< 180), it's a wrapped continued option!
                                if w < 180:
                                    if len(current_block['options']) >= 4 and first_page_block is not None and current_block != first_page_block:
                                        current_block = first_page_block
                                        
                                    current_block['options'].append({
                                        'box': (p_idx, (el['x0'], el['top'], el['x1'], el['bottom'])),
                                        'top': el['top'],
                                        'is_correct': False,
                                        'path': ""
                                    })
                                else:
                                    current_block['gujarati_prompt_box'] = (p_idx, (el['x0'], el['top'], el['x1'], el['bottom']))
                            else:
                                # Normal option text image (starts at x0 >= 55)
                                if len(current_block['options']) >= 4 and first_page_block is not None and current_block != first_page_block:
                                    current_block = first_page_block
                                    
                                current_block['options'].append({
                                    'box': (p_idx, (el['x0'], el['top'], el['x1'], el['bottom'])),
                                    'top': el['top'],
                                    'is_correct': False,
                                    'path': ""
                                })

        # Step 2: Merge raw blocks by unique Question Id
        print(f"\nMerging {len(raw_blocks)} raw blocks...")
        merged_questions = {}
        for block in raw_blocks:
            q_id = block['id']
            if q_id not in merged_questions:
                merged_questions[q_id] = {
                    'number': block['number'],
                    'id': q_id,
                    'english_prompt': "",
                    'gujarati_prompt_box': None,
                    'gujarati_prompt_path': "",
                    'options': [],
                    'temp_options_icons': []
                }
                
            mq = merged_questions[q_id]
            
            # A. Select English prompt (the block containing non-empty text)
            if len(block['english_prompt']) > len(mq['english_prompt']):
                mq['english_prompt'] = block['english_prompt']
                
            # B. Select Gujarati prompt (the block containing the large prompt image)
            if block['gujarati_prompt_box'] is not None:
                mq['gujarati_prompt_box'] = block['gujarati_prompt_box']
                
            # C. Select Options (keep the first block that has options to avoid duplicate option dumps)
            if len(mq['options']) < 4 and len(block['options']) > 0:
                mq['options'] = block['options']
                mq['temp_options_icons'] = block['temp_options_icons']

        # Convert dictionary to sorted list
        questions_list = list(merged_questions.values())
        questions_list.sort(key=lambda q: q['number'])
        print(f"Final merged questions count: {len(questions_list)}")
        
        # Step 3: Crop and export assets
        print("\nCropping and exporting question assets...")
        for q_idx, q in enumerate(questions_list, 1):
            exam_id_folder = exam_assets_dir
            
            # Sort temp_options_icons by top
            q['temp_options_icons'].sort(key=lambda x: x['top'])
            
            # SELF-HEALING / FALLBACK: If we have less than 4 option images, but we have at least 4 icons,
            # we discard the incomplete/broken options and generate all 4 options dynamically
            # by cropping the text region to the right of each icon (starting at x0=60.0)
            if len(q['options']) < 4 and len(q['temp_options_icons']) >= 4:
                q['options'] = []
                p_num = q['gujarati_prompt_box'][0] if q['gujarati_prompt_box'] else 0
                # Take the first 4 icons (since they correspond to options A, B, C, D)
                for icon in q['temp_options_icons'][:4]:
                    q['options'].append({
                        'box': (p_num, (60.0, icon['top'] - 2, 450.0, icon['bottom'] + 2)),
                        'top': icon['top'],
                        'bottom': icon['bottom'],
                        'is_correct': icon['is_correct'],
                        'path': ""
                    })
            
            # Crop prompt image
            if q['gujarati_prompt_box']:
                p_num, bbox = q['gujarati_prompt_box']
                prompt_filename = f"q{q['number']}_prompt.png"
                prompt_path = os.path.join(exam_id_folder, prompt_filename)
                
                try:
                    with pdfplumber.open(pdf_path) as pdf_crop:
                        crop_page = pdf_crop.pages[p_num]
                        x0 = max(0, bbox[0] - 2)
                        top = max(0, bbox[1] - 2)
                        x1 = min(crop_page.width, bbox[2] + 2)
                        bottom = min(crop_page.height, bbox[3] + 2)
                        
                        cropped_page = crop_page.crop((x0, top, x1, bottom))
                        cropped_page.to_image(resolution=150).save(prompt_path)
                        q['gujarati_prompt_path'] = f"exams/{exam_id}/{prompt_filename}"
                except Exception as e:
                    print(f"  Error cropping question {q['number']} prompt: {e}")
            
            # Crop options images and verify answer icons
            q['options'].sort(key=lambda x: x['top'])
            
            correct_idx = -1
            
            # Keep only first 4 options
            opts_to_crop = q['options'][:4]
            
            for o_idx, opt in enumerate(opts_to_crop):
                # Read bottom coordinate from box list if present, else fallback
                opt_bottom = opt['box'][1][3] if 'box' in opt else (opt['bottom'] if 'bottom' in opt else (opt['top'] + 25))
                
                # Check correct option icon vertically aligned using vertical overlap
                closest_icon = None
                for icon in q['temp_options_icons']:
                    # Calculate overlap between opt vertical span and icon vertical span
                    overlap = max(0, min(opt_bottom, icon['bottom']) - max(opt['top'], icon['top']))
                    if overlap > 0:
                        closest_icon = icon
                        break
                        
                if closest_icon:
                    opt['is_correct'] = closest_icon['is_correct']
                    if closest_icon['is_correct']:
                        correct_idx = o_idx
                
                # Crop image if it's an image option
                if 'text' in opt and opt['text'] != "":
                    opt['path'] = ""
                else:
                    p_num, bbox = opt['box']
                    opt_filename = f"q{q['number']}_opt{o_idx+1}.png"
                    opt_path = os.path.join(exam_id_folder, opt_filename)
                    
                    try:
                        with pdfplumber.open(pdf_path) as pdf_crop:
                            crop_page = pdf_crop.pages[p_num]
                            # Crop starting at x0=60.0 to exclude the WAF/PDF checkmark icons
                            x0 = max(60.0, bbox[0])
                            top = max(0, bbox[1] - 2)
                            x1 = min(crop_page.width, bbox[2] + 2)
                            bottom = min(crop_page.height, bbox[3] + 2)
                            
                            cropped_page = crop_page.crop((x0, top, x1, bottom))
                            cropped_page.to_image(resolution=150).save(opt_path)
                            opt['path'] = f"exams/{exam_id}/{opt_filename}"
                    except Exception as e:
                         # Print message but do not halt
                         pass
            
            q['correct_option_index'] = correct_idx
            q['options'] = opts_to_crop
            
            # Clean up temp keys
            if 'temp_options_icons' in q:
                del q['temp_options_icons']
            for opt in q['options']:
                if 'box' in opt:
                    del opt['box']
                if 'top' in opt:
                    del opt['top']
                if 'bottom' in opt:
                    del opt['bottom']
            if 'gujarati_prompt_box' in q:
                del q['gujarati_prompt_box']
                    
            if q_idx % 10 == 0 or q_idx == len(questions_list):
                print(f"  Processed {q_idx}/{len(questions_list)} questions")

    # Save metadata JS (to bypass CORS on file:// protocol)
    meta_js_path = os.path.join(exam_assets_dir, "questions.js")
    with open(meta_js_path, "w", encoding="utf-8") as f:
        clean_questions = []
        for q in questions_list:
            clean_questions.append({
                "number": q["number"],
                "id": q["id"],
                "english_prompt": q["english_prompt"],
                "gujarati_prompt_path": q["gujarati_prompt_path"],
                "correct_option_index": q["correct_option_index"],
                "options": [
                    {
                        "index": opt.get("index", i+1),
                        "path": opt.get("path", ""),
                        "text": opt.get("text", "")
                    } for i, opt in enumerate(q["options"])
                ]
            })
        f.write("window.examQuestions = ")
        json.dump(clean_questions, f, ensure_ascii=False, indent=2)
        f.write(";")
        
    print(f"\nSuccessfully imported {len(clean_questions)} questions for exam '{exam_id}'!")
    print(f"Metadata saved in: {meta_js_path}")
    return len(clean_questions)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_exam.py <pdf_path>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    output_dir = os.path.dirname(os.path.abspath(__file__))
    parse_pdf(pdf_path, output_dir)
