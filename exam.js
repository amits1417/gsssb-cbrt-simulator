// TCS/GSSSB Online CBRT Exam Simulator Javascript Logic

let questions = [];
let currentIndex = 0;
let answers = []; // Stores user answers (1-5 where 5 is E) or null
let statuses = []; // Stores question statuses: 'not-visited', 'not-answered', 'answered', 'marked', 'marked-answered'
let timerSeconds = 3600; // 60 minutes default
let timerInterval = null;
let currentExamId = "";

// Available exams list
const availableExams = window.availableExams || [
    { id: "PAPER-1", name: "Paper-1 Combined Competitive Exam (Group A & B)" },
    { id: "PAPER-2", name: "Paper-2 Combined Competitive Exam (Group A & B)" }
];

document.addEventListener("DOMContentLoaded", () => {
    initExamSelection();
    initEventListeners();
});

function initExamSelection() {
    const selector = document.getElementById("examSelect");
    if (!selector) return;
    
    // Clear and fill dropdown
    selector.innerHTML = `<option value="">-- Choose Exam Paper --</option>`;
    availableExams.forEach(exam => {
        selector.innerHTML += `<option value="${exam.id}">${exam.name}</option>`;
    });
}

function initEventListeners() {
    // Navigation buttons
    document.getElementById("btnClear").addEventListener("click", clearResponse);
    document.getElementById("btnMarkNext").addEventListener("click", markForReviewAndNext);
    document.getElementById("btnSaveNext").addEventListener("click", saveAndNext);
    document.getElementById("btnSubmit").addEventListener("click", showSubmitModal);
    
    // Modal buttons
    document.getElementById("modalClose").addEventListener("click", closeSubmitModal);
    document.getElementById("modalSubmit").addEventListener("click", submitExam);
    
    // Option rows click handler (to check radio on row click)
    // We delegate to document to ensure it works dynamically for any elements
    document.addEventListener("click", (e) => {
        const row = e.target.closest(".option-row");
        if (row) {
            const radio = row.querySelector('input[type="radio"]');
            if (radio && e.target !== radio) {
                radio.checked = true;
            }
        }
    });
}

function startSelectedExam() {
    const selector = document.getElementById("examSelect");
    const examId = selector.value;
    if (!examId) {
        alert("Please select an exam first!");
        return;
    }
    
    currentExamId = examId;
    
    // Hide home screen, show exam screen
    document.getElementById("homeScreen").style.display = "none";
    document.getElementById("examScreen").style.display = "block";
    
    // Load question data dynamically using script tag to bypass CORS on file:// protocol
    const oldScript = document.getElementById("examDataScript");
    if (oldScript) oldScript.remove();
    
    const script = document.createElement("script");
    script.id = "examDataScript";
    script.src = `exams/${examId}/questions.js`;
    script.onload = () => {
        if (window.examQuestions) {
            questions = window.examQuestions;
            initExamState();
        } else {
            alert("Error: Questions not found in loaded exam script.");
        }
    };
    script.onerror = () => {
        alert("Exam data not found. Please run the import script first!");
        // Go back to home
        document.getElementById("homeScreen").style.display = "block";
        document.getElementById("examScreen").style.display = "none";
    };
    document.body.appendChild(script);
}

function initExamState() {
    currentIndex = 0;
    answers = new Array(questions.length).fill(null);
    statuses = new Array(questions.length).fill("not-visited");
    
    // Set first question as active
    statuses[0] = "not-answered";
    
    // Build palette grid
    buildPaletteGrid();
    
    // Load first question
    loadQuestion(0);
    
    // Start Timer
    timerSeconds = 3600; // 60 mins
    updateTimerDisplay();
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        timerSeconds--;
        updateTimerDisplay();
        if (timerSeconds <= 0) {
            clearInterval(timerInterval);
            alert("Time's up! Submitting exam.");
            submitExam();
        }
    }, 1000);
}

function buildPaletteGrid() {
    const grid = document.getElementById("paletteGrid");
    grid.innerHTML = "";
    
    questions.forEach((q, idx) => {
        const btn = document.createElement("button");
        btn.id = `palBtn_${idx}`;
        btn.className = "palette-btn not-visited";
        btn.innerText = idx + 1;
        btn.addEventListener("click", () => jumpToQuestion(idx));
        grid.appendChild(btn);
    });
    
    updatePaletteDisplay();
}

function updatePaletteDisplay() {
    questions.forEach((q, idx) => {
        const btn = document.getElementById(`palBtn_${idx}`);
        if (!btn) return;
        
        // Remove all status classes
        btn.className = "palette-btn";
        
        // Add active status class
        const status = statuses[idx];
        btn.classList.add(status);
        
        // Add active class highlight
        if (idx === currentIndex) {
            btn.style.border = "2px solid #000";
            btn.style.fontWeight = "bold";
        } else {
            btn.style.border = "";
            btn.style.fontWeight = "";
        }
    });
}

function loadQuestion(index) {
    currentIndex = index;
    const q = questions[index];
    
    // Set Question numbers
    document.getElementById("qNumberTitle").innerText = `Question No. ${q.number}`;
    
    // Set prompts
    document.getElementById("qTextEng").innerText = q.english_prompt;
    
    const gujImg = document.getElementById("qImgGuj");
    if (q.gujarati_prompt_path) {
        gujImg.src = q.gujarati_prompt_path;
        gujImg.style.display = "block";
    } else {
        gujImg.style.display = "none";
    }
    
    // Uncheck all radios initially (including option E which is static)
    for (let optNum = 1; optNum <= 5; optNum++) {
        const optRow = document.getElementById(`optRow_${optNum}`);
        const optRadio = document.getElementById(`optRadio_${optNum}`);
        optRadio.checked = false;
        optRow.style.display = "flex"; // reset display
        
        // Clear dynamically created text span if any
        const textSpan = optRow.querySelector('.opt-text-val');
        if (textSpan) textSpan.remove();
    }
    
    // Check if the question is cancelled / ignored (no options)
    if (q.options.length === 0) {
        // Display cancellation message and hide A, B, C, D options
        document.getElementById("qTextEng").innerText = q.english_prompt + "\n\n[Note: For this question, discrepancy was found in the question/answer. So, this question is IGNORED for all candidates.]";
        for (let optNum = 1; optNum <= 4; optNum++) {
            document.getElementById(`optRow_${optNum}`).style.display = "none";
        }
        // Force option E to show and check it as "Not Attempted" automatically
        document.getElementById("optRadio_5").checked = true;
        answers[index] = 5;
    } else {
        // Set options (A, B, C, D)
        q.options.forEach((opt, oIdx) => {
            const optNum = oIdx + 1;
            const optRow = document.getElementById(`optRow_${optNum}`);
            const optRadio = document.getElementById(`optRadio_${optNum}`);
            const optImg = document.getElementById(`optImg_${optNum}`);
            
            if (opt.text) {
                // Render as Text Option
                optImg.style.display = "none";
                const span = document.createElement("span");
                span.className = "opt-text-val";
                span.innerText = opt.text;
                span.style.marginLeft = "8px";
                span.style.fontWeight = "bold";
                span.style.fontSize = "15px";
                span.style.color = "#2c3e50";
                optRadio.parentNode.appendChild(span);
            } else {
                // Render as Image Option
                optImg.src = opt.path;
                optImg.style.display = "block";
            }
        });
    }
    
    // Load previously selected answer
    const savedAnswer = answers[index];
    if (savedAnswer !== null) {
        document.getElementById(`optRadio_${savedAnswer}`).checked = true;
    }
    
    // Update question status
    if (statuses[index] === "not-visited") {
        statuses[index] = "not-answered";
    }
    
    updatePaletteDisplay();
}

function jumpToQuestion(index) {
    // Save state of current question if it was answered
    saveState();
    loadQuestion(index);
}

function saveState() {
    const selectedRadio = document.querySelector('input[name="examOption"]:checked');
    if (selectedRadio) {
        const val = parseInt(selectedRadio.value); // 1-5
        answers[currentIndex] = val;
        
        // Check if marked
        if (statuses[currentIndex] === "marked" || statuses[currentIndex] === "marked-answered") {
            statuses[currentIndex] = "marked-answered";
        } else {
            statuses[currentIndex] = "answered";
        }
    } else {
        // No option selected
        if (answers[currentIndex] === null) {
            if (statuses[currentIndex] === "marked" || statuses[currentIndex] === "marked-answered") {
                statuses[currentIndex] = "marked";
            } else {
                statuses[currentIndex] = "not-answered";
            }
        }
    }
}

function saveAndNext() {
    saveState();
    if (currentIndex < questions.length - 1) {
        loadQuestion(currentIndex + 1);
    } else {
        alert("This is the last question.");
        updatePaletteDisplay();
    }
}

function markForReviewAndNext() {
    const selectedRadio = document.querySelector('input[name="examOption"]:checked');
    if (selectedRadio) {
        answers[currentIndex] = parseInt(selectedRadio.value);
        statuses[currentIndex] = "marked-answered";
    } else {
        statuses[currentIndex] = "marked";
    }
    
    if (currentIndex < questions.length - 1) {
        loadQuestion(currentIndex + 1);
    } else {
        alert("This is the last question.");
        updatePaletteDisplay();
    }
}

function clearResponse() {
    // If the question is cancelled, prevent clearing (must stay E / Unattempted)
    const q = questions[currentIndex];
    if (q.options.length === 0) {
        return;
    }
    
    const selectedRadio = document.querySelector('input[name="examOption"]:checked');
    if (selectedRadio) {
        selectedRadio.checked = false;
    }
    answers[currentIndex] = null;
    if (statuses[currentIndex] === "marked-answered" || statuses[currentIndex] === "marked") {
        statuses[currentIndex] = "marked";
    } else {
        statuses[currentIndex] = "not-answered";
    }
    updatePaletteDisplay();
}

function updateTimerDisplay() {
    const mins = Math.floor(timerSeconds / 60);
    const secs = timerSeconds % 60;
    document.getElementById("timer").innerText = `Time Left: ${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function showSubmitModal() {
    saveState();
    
    // Calculate counts
    let answered = 0;
    let notAnswered = 0;
    let marked = 0;
    let markedAnswered = 0;
    let notVisited = 0;
    
    statuses.forEach(status => {
        if (status === "answered") answered++;
        else if (status === "not-answered") notAnswered++;
        else if (status === "marked") marked++;
        else if (status === "marked-answered") markedAnswered++;
        else if (status === "not-visited") notVisited++;
    });
    
    document.getElementById("statAnswered").innerText = answered;
    document.getElementById("statNotAnswered").innerText = notAnswered;
    document.getElementById("statMarked").innerText = marked;
    document.getElementById("statMarkedAnswered").innerText = markedAnswered;
    document.getElementById("statNotVisited").innerText = notVisited;
    
    document.getElementById("submitModal").style.display = "flex";
}

function closeSubmitModal() {
    document.getElementById("submitModal").style.display = "none";
}

function submitExam() {
    clearInterval(timerInterval);
    closeSubmitModal();
    
    // Evaluate results
    let totalQuestions = questions.length;
    let correct = 0;
    let incorrect = 0;
    let unattempted = 0;
    
    const reviewContainer = document.getElementById("reviewContainer");
    reviewContainer.innerHTML = "";
    
    questions.forEach((q, idx) => {
        const userAns = answers[idx]; // 1-5 where 5 is E (Not Attempted)
        const correctAnsIndex = q.correct_option_index; // 0-3 (representing A-D)
        const correctAns = correctAnsIndex + 1; // 1-4
        
        let scoreForQuestion = 0.0;
        let isCorrect = false;
        let isUnattempted = false;
        let isCancelled = correctAnsIndex === -1;
        
        if (isCancelled) {
            unattempted++;
            isUnattempted = true;
            scoreForQuestion = 0.0;
        } else if (userAns === null || userAns === 5) {
            unattempted++;
            isUnattempted = true;
            scoreForQuestion = 0.0;
        } else if (userAns === correctAns) {
            correct++;
            isCorrect = true;
            scoreForQuestion = 1.0;
        } else {
            incorrect++;
            scoreForQuestion = -0.25;
        }
        
        // Build review card details
        let cardBorderColor = "#7f8c8d"; // Gray for unattempted/cancelled
        let cardBgColor = "#f1f2f6";
        let statusColor = "#7f8c8d";
        let statusText = `Unattempted (Score: 0.00)`;
        
        if (isCancelled) {
            statusText = `Cancelled Question (Score: 0.00)`;
        } else if (isCorrect) {
            cardBorderColor = "#20bf6b"; // Green
            cardBgColor = "#e3fcef";
            statusColor = "#20bf6b";
            statusText = `Correct (Score: +1.00)`;
        } else if (!isUnattempted) {
            cardBorderColor = "#eb3b5a"; // Red
            cardBgColor = "#ffeef0";
            statusColor = "#eb3b5a";
            statusText = `Incorrect (Score: -0.25)`;
        }
        
        // Generate options review UI
        let optionsHtml = "";
        
        if (isCancelled) {
            optionsHtml = `<div style="padding: 10px; border: 1.5px dashed #eb3b5a; background-color: #ffeef0; color: #eb3b5a; font-weight: bold; border-radius: 4px;">Discrepancy found. This question is ignored for all candidates.</div>`;
        } else {
            optionsHtml = q.options.map((opt, oIdx) => {
                const optNum = oIdx + 1;
                const isUserSelected = userAns === optNum;
                const isRightOption = correctAns === optNum;
                
                let optStyle = "padding: 6px 12px; border: 1.5px solid #ddd; border-radius: 4px; display: flex; align-items: center; gap: 10px; background-color: white; margin-bottom: 5px;";
                if (isRightOption) {
                    optStyle = "padding: 6px 12px; border: 1.5px solid #20bf6b; border-radius: 4px; display: flex; align-items: center; gap: 10px; background-color: #d4edda; font-weight: bold; margin-bottom: 5px;";
                } else if (isUserSelected) {
                    optStyle = "padding: 6px 12px; border: 1.5px solid #eb3b5a; border-radius: 4px; display: flex; align-items: center; gap: 10px; background-color: #f8d7da; margin-bottom: 5px;";
                }
                
                let badgeHtml = "";
                if (isRightOption && isUserSelected) {
                    badgeHtml = `<span style="color: #155724; font-size: 11px; margin-left: auto; background-color: #c3e6cb; padding: 2px 6px; border-radius: 3px;">Your Choice & Correct</span>`;
                } else if (isRightOption) {
                    badgeHtml = `<span style="color: #155724; font-size: 11px; margin-left: auto; background-color: #c3e6cb; padding: 2px 6px; border-radius: 3px;">Correct Answer</span>`;
                } else if (isUserSelected) {
                    badgeHtml = `<span style="color: #721c24; font-size: 11px; margin-left: auto; background-color: #f5c6cb; padding: 2px 6px; border-radius: 3px;">Your Choice (Incorrect)</span>`;
                }
                
                let optContent = "";
                if (opt.text) {
                    optContent = `<span>${opt.text}</span>`;
                } else {
                    optContent = `<img src="${opt.path}" style="max-height: 25px; vertical-align: middle;">`;
                }
                
                return `
                    <div style="${optStyle}">
                        <span style="font-weight: bold; color: #4b6584;">${String.fromCharCode(65 + oIdx)}.</span>
                        ${optContent}
                        ${badgeHtml}
                    </div>
                `;
            }).join('');
            
            // Add static option E review row
            let optEStyle = "padding: 6px 12px; border: 1.5px solid #ddd; border-radius: 4px; display: flex; align-items: center; gap: 10px; background-color: white;";
            let eBadge = "";
            if (userAns === 5) {
                optEStyle = "padding: 6px 12px; border: 1.5px solid #7f8c8d; border-radius: 4px; display: flex; align-items: center; gap: 10px; background-color: #e2e3e5; font-weight: bold;";
                eBadge = `<span style="color: #383d41; font-size: 11px; margin-left: auto; background-color: #d6d8db; padding: 2px 6px; border-radius: 3px;">Your Choice</span>`;
            }
            
            optionsHtml += `
                <div style="${optEStyle}">
                    <span style="font-weight: bold; color: #4b6584;">E.</span>
                    <span>Not Attempted (અનએટેમ્પ્ટેડ)</span>
                    ${eBadge}
                </div>
            `;
        }
        
        // Assemble card
        const cardHtml = `
            <div style="border: 1.5px solid ${cardBorderColor}; background-color: ${cardBgColor}; padding: 15px; margin-bottom: 20px; border-radius: 6px;">
                <div style="font-weight: bold; font-size: 14px; border-bottom: 1.5px solid #ccd; padding-bottom: 6px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #2c3e50;">Question No. ${q.number}</span>
                    <span style="color: ${statusColor}; font-weight: bold; font-size: 13px;">${statusText}</span>
                </div>
                <div style="font-size: 15px; line-height: 1.4; color: #2c3e50; margin-bottom: 10px; font-weight: 500;">
                    ${q.english_prompt.replace(/\n/g, '<br>')}
                </div>
                ${q.gujarati_prompt_path ? `<img src="${q.gujarati_prompt_path}" style="max-width: 100%; display: block; margin-bottom: 15px; border: 1px solid #ddd; padding: 4px; background-color: white;">` : ''}
                
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    ${optionsHtml}
                </div>
            </div>
        `;
        
        reviewContainer.innerHTML += cardHtml;
    });
    
    const rawScore = correct * 1.0 - incorrect * 0.25;
    
    // Hide exam screen, show results screen
    document.getElementById("examScreen").style.display = "none";
    document.getElementById("resultsScreen").style.display = "block";
    
    // Fill result details
    document.getElementById("resTotal").innerText = totalQuestions;
    document.getElementById("resCorrect").innerText = correct;
    document.getElementById("resIncorrect").innerText = incorrect;
    document.getElementById("resUnattempted").innerText = unattempted;
    document.getElementById("resScore").innerText = rawScore.toFixed(2);
}

function backToHome() {
    document.getElementById("resultsScreen").style.display = "none";
    document.getElementById("homeScreen").style.display = "block";
    initExamSelection();
}
