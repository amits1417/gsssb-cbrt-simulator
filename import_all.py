import os
import glob
import multiprocessing
import import_exam
import json

def process_paper(pdf_path):
    paper_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_dir = os.path.dirname(os.path.abspath(__file__))
    questions_file = os.path.join(output_dir, "exams", paper_name, "questions.js")
    
    # Skip if questions.js already exists and is non-empty
    if os.path.exists(questions_file) and os.path.getsize(questions_file) > 0:
        print(f"Skipping {paper_name} (already imported).")
        return paper_name, True
        
    print(f"Starting import of {paper_name}...")
    try:
        import_exam.parse_pdf(pdf_path, output_dir)
        print(f"Finished importing {paper_name}.")
        return paper_name, True
    except Exception as e:
        print(f"Error importing {paper_name}: {e}")
        return paper_name, False

def main():
    papers_dir = r"C:\Users\admin\.gemini\antigravity\scratch\GSSSB_Papers"
    pdf_files = glob.glob(os.path.join(papers_dir, "PAPER-*.pdf"))
    
    # Sort files numerically
    def get_num(filepath):
        basename = os.path.splitext(os.path.basename(filepath))[0]
        num_str = basename.replace("PAPER-", "")
        try:
            return int(num_str)
        except ValueError:
            return 999
            
    pdf_files.sort(key=get_num)
    
    print(f"Found {len(pdf_files)} GSSSB exam papers.")
    
    # Run in parallel
    num_workers = min(multiprocessing.cpu_count(), 6) # limit to max 6 workers to avoid choking
    print(f"Running import with {num_workers} parallel workers...")
    
    pool = multiprocessing.Pool(processes=num_workers)
    results = pool.map(process_paper, pdf_files)
    pool.close()
    pool.join()
    
    # Generate exams_list.js
    output_dir = os.path.dirname(os.path.abspath(__file__))
    exams_list_path = os.path.join(output_dir, "exams_list.js")
    
    available_exams = []
    for pdf_path in pdf_files:
        paper_name = os.path.splitext(os.path.basename(pdf_path))[0]
        questions_file = os.path.join(output_dir, "exams", paper_name, "questions.js")
        if os.path.exists(questions_file):
            num = get_num(pdf_path)
            display_name = f"Paper-{num} Combined Competitive Exam"
            available_exams.append({
                "id": paper_name,
                "name": display_name
            })
            
    with open(exams_list_path, "w", encoding="utf-8") as f:
        f.write("window.availableExams = ")
        json.dump(available_exams, f, indent=2)
        f.write(";")
        
    print(f"\nExams list generated successfully at {exams_list_path}!")
    print(f"Total exams imported: {len(available_exams)}/{len(pdf_files)}")

if __name__ == "__main__":
    main()
