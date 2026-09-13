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

function togglePaletteDrawer(show) {
    const sidebar = document.getElementById("sidebarPanel");
    const backdrop = document.getElementById("paletteBackdrop");
    if (!sidebar) return;
    if (show === undefined) {
        const isOpen = sidebar.classList.toggle("open");
        if (backdrop) backdrop.classList.toggle("active", isOpen);
    } else if (show) {
        sidebar.classList.add("open");
        if (backdrop) backdrop.classList.add("active");
    } else {
        sidebar.classList.remove("open");
        if (backdrop) backdrop.classList.remove("active");
    }
}

function buildPaletteGrid() {
    const grid = document.getElementById("paletteGrid");
    if (!grid) return;
    grid.innerHTML = "";
    
    questions.forEach((q, idx) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.id = `palBtn_${idx}`;
        btn.className = "palette-btn not-visited";
        btn.innerText = idx + 1;
        btn.onclick = function(e) {
            if (e) { e.preventDefault(); e.stopPropagation(); }
            jumpToQuestion(idx);
        };
        grid.appendChild(btn);
    });
    
    updatePaletteDisplay();
}

function updatePaletteDisplay() {
    let answered = 0;
    questions.forEach((q, idx) => {
        const btn = document.getElementById(`palBtn_${idx}`);
        if (!btn) return;
        
        // Remove all status classes
        btn.className = "palette-btn";
        
        // Add active status class
        const status = statuses[idx];
        btn.classList.add(status);
        if (status === "answered" || status === "marked-answered") answered++;
        
        // Add active class highlight
        if (idx === currentIndex) {
            btn.style.border = "2px solid #000";
            btn.style.fontWeight = "bold";
        } else {
            btn.style.border = "";
            btn.style.fontWeight = "";
        }
    });
    const badge = document.getElementById("paletteAnsweredBadge");
    if (badge) badge.innerText = answered;
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
    togglePaletteDrawer(false); // Auto-close drawer on mobile
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
    const reviewDataList = [];
    
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
        
        let status = isCancelled ? 'cancelled' : (isCorrect ? 'correct' : (isUnattempted ? 'unattempted' : 'incorrect'));
        reviewDataList.push({
            number: q.number,
            id: q.id || '',
            english_prompt: q.english_prompt || '',
            gujarati_prompt_path: q.gujarati_prompt_path || '',
            options: q.options || [],
            user_ans: userAns,
            correct_ans: isCancelled ? null : correctAns,
            is_cancelled: isCancelled,
            is_correct: isCorrect,
            status: status
        });
    });

    latestReviewData = {
        paper_id: currentExamId,
        total_questions: totalQuestions,
        correct_count: correct,
        incorrect_count: incorrect,
        unattempted_count: unattempted,
        net_score: (correct * 1.0 - incorrect * 0.25).toFixed(2),
        review: reviewDataList
    };

    renderExamResultsUI(latestReviewData);
}

let latestReviewData = null;

function toggleJumpGrid() {
    const grid = document.getElementById("jumpPaletteContainer");
    const icon = document.getElementById("jumpToggleIcon");
    if (!grid) return;
    if (grid.style.display === "none") {
        grid.style.display = "grid";
        if (icon) icon.className = "fa-solid fa-chevron-up";
    } else {
        grid.style.display = "none";
        if (icon) icon.className = "fa-solid fa-chevron-down";
    }
}

function filterReviewQuestions(type, btnElem) {
    document.querySelectorAll(".filter-tab-btn").forEach(b => b.classList.remove("active"));
    if (btnElem) btnElem.classList.add("active");

    const cards = document.querySelectorAll(".review-card");
    cards.forEach(card => {
        const cardStatus = card.getAttribute("data-status");
        if (type === 'all') {
            card.style.display = "block";
        } else if (type === 'correct' && cardStatus === 'correct') {
            card.style.display = "block";
        } else if (type === 'incorrect' && cardStatus === 'incorrect') {
            card.style.display = "block";
        } else if (type === 'unattempted' && (cardStatus === 'unattempted' || cardStatus === 'cancelled')) {
            card.style.display = "block";
        } else {
            card.style.display = "none";
        }
    });
}

function renderExamResultsUI(resData) {
    document.getElementById("examScreen").style.display = "none";
    document.getElementById("resultsScreen").style.display = "block";
    document.getElementById("resultsScreen").scrollTop = 0;

    const titleElem = document.getElementById("resultsExamTitle");
    if (titleElem) {
        titleElem.innerHTML = `<strong>${resData.paper_id}</strong> &bull; GSSSB Combined Competitive Exam (CCE Group A & B)`;
    }

    document.getElementById("resTotal").innerText = resData.total_questions;
    document.getElementById("resCorrect").innerText = resData.correct_count;
    document.getElementById("resIncorrect").innerText = resData.incorrect_count;
    document.getElementById("resUnattempted").innerText = resData.unattempted_count;
    document.getElementById("resScore").innerText = resData.net_score;

    const fAll = document.getElementById("filterAllBtn");
    if (fAll) fAll.innerText = `All Questions (${resData.total_questions})`;
    const fCorr = document.getElementById("filterCorrectBtn");
    if (fCorr) fCorr.innerText = `✔ Correct (${resData.correct_count})`;
    const fIncorr = document.getElementById("filterIncorrectBtn");
    if (fIncorr) fIncorr.innerText = `✖ Incorrect (${resData.incorrect_count})`;
    const fUnatt = document.getElementById("filterUnattemptedBtn");
    if (fUnatt) fUnatt.innerText = `⚪ Unattempted / E (${resData.unattempted_count})`;

    const reviewContainer = document.getElementById("reviewContainer");
    reviewContainer.innerHTML = "";

    const jumpPalette = document.getElementById("jumpPaletteContainer");
    if (jumpPalette) jumpPalette.innerHTML = "";

    resData.review.forEach(q => {
        const uAns = q.user_ans;
        const cAns = q.correct_ans;
        const isCancelled = q.is_cancelled;
        const isCorrect = q.is_correct;
        const isUnattempted = (q.status === 'unattempted');

        if (jumpPalette) {
            const jumpBadge = document.createElement("a");
            jumpBadge.href = `#review-q-${q.number}`;
            jumpBadge.innerText = q.number;
            if (isCancelled) {
                jumpBadge.className = "jump-badge jump-badge-cancelled";
            } else if (isCorrect) {
                jumpBadge.className = "jump-badge jump-badge-correct";
            } else if (isUnattempted) {
                jumpBadge.className = "jump-badge jump-badge-unattempted";
            } else {
                jumpBadge.className = "jump-badge jump-badge-incorrect";
            }
            jumpPalette.appendChild(jumpBadge);
        }

        const card = document.createElement("div");
        card.id = `review-q-${q.number}`;
        card.className = "review-card";
        card.setAttribute("data-status", q.status);
        card.style.borderColor = isCancelled ? '#94a3b8' : (isCorrect ? '#86efac' : (isUnattempted ? '#cbd5e1' : '#fca5a5'));

        let optionsHtml = '<div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px;">';
        if (isCancelled) {
            optionsHtml += `<div style="padding: 12px 18px; border: 1.5px dashed #dc2626; background: #fee2e2; color: #dc2626; font-weight: 700; border-radius: 8px;">Discrepancy found. This question is ignored for all candidates (0.00 Marks).</div>`;
        } else {
            (q.options || []).forEach((opt, oIdx) => {
                const optNum = oIdx + 1;
                const optLetter = String.fromCharCode(64 + optNum);
                const isThisCorrect = (cAns === optNum);
                const isThisChosen = (uAns === optNum);

                let optBorder = '#e2e8f0';
                let optBg = '#ffffff';
                let badgeHtml = '';

                if (isThisCorrect && isThisChosen) {
                    optBorder = '#16a34a';
                    optBg = '#dcfce7';
                    badgeHtml = `<span style="background: #16a34a; color: white; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 800; margin-left: auto; white-space: nowrap;"><i class="fa-solid fa-circle-check"></i> Correct & Selected (+1.00)</span>`;
                } else if (isThisCorrect) {
                    optBorder = '#16a34a';
                    optBg = '#f0fdf4';
                    badgeHtml = `<span style="background: #16a34a; color: white; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 800; margin-left: auto; white-space: nowrap;"><i class="fa-solid fa-check"></i> Official Correct</span>`;
                } else if (isThisChosen) {
                    optBorder = '#dc2626';
                    optBg = '#fee2e2';
                    badgeHtml = `<span style="background: #dc2626; color: white; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 800; margin-left: auto; white-space: nowrap;"><i class="fa-solid fa-xmark"></i> Your Selection (Wrong, -0.25)</span>`;
                }

                optionsHtml += `
                    <div style="display: flex; align-items: center; gap: 12px; border: 1.5px solid ${optBorder}; background: ${optBg}; padding: 12px 18px; border-radius: 8px; font-size: 15.5px;">
                        <span style="font-size: 16px; font-weight: 800; color: ${isThisCorrect ? '#16a34a' : (isThisChosen ? '#dc2626' : '#3867d6')}; min-width: 28px;">${optLetter}.</span>
                        <div style="flex-grow: 1; font-size: 15.5px; color: #1e293b;">
                            ${opt.path ? `<img src="${opt.path}" style="max-height: 55px; max-width: 85%; vertical-align: middle;">` : `<span>${opt.text || ('Option ' + optLetter)}</span>`}
                        </div>
                        ${badgeHtml}
                    </div>
                `;
            });

            if (uAns === 5) {
                optionsHtml += `
                    <div style="display: flex; align-items: center; gap: 12px; border: 1.5px solid #94a3b8; background: #f1f5f9; padding: 12px 18px; border-radius: 8px; font-size: 15.5px;">
                        <span style="font-size: 16px; font-weight: 800; color: #475569; min-width: 28px;">E.</span>
                        <div style="flex-grow: 1; font-size: 15.5px; color: #475569; font-weight: 600;">Not Attempted (અનએટેમ્પ્ટેડ)</div>
                        <span style="background: #64748b; color: white; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 800; margin-left: auto; white-space: nowrap;">Your Selection (0.00 Marks)</span>
                    </div>
                `;
            }
        }
        optionsHtml += '</div>';

        let statusBadgeText = '';
        if (isCancelled) {
            statusBadgeText = `<span style="color: #475569; background: #e2e8f0; padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 800;"><i class="fa-solid fa-triangle-exclamation"></i> Cancelled (0.00 Marks)</span>`;
        } else if (isCorrect) {
            statusBadgeText = `<span style="color: #15803d; background: #dcfce7; border: 1px solid #86efac; padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 800;"><i class="fa-solid fa-circle-check"></i> Correct (+1.00 Mark)</span>`;
        } else if (isUnattempted) {
            statusBadgeText = `<span style="color: #64748b; background: #f1f5f9; border: 1px solid #cbd5e1; padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 800;">— Unattempted (0.00 Marks)</span>`;
        } else {
            statusBadgeText = `<span style="color: #b91c1c; background: #fee2e2; border: 1px solid #fca5a5; padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 800;"><i class="fa-solid fa-circle-xmark"></i> Incorrect (-0.25 Mark)</span>`;
        }

        let cleanPrompt = (q.english_prompt || '').replace(/^Yes\s*/i, '').trim();

        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid #f1f5f9; padding-bottom: 12px; margin-bottom: 16px;">
                <span style="font-size: 18px; font-weight: 800; color: #1e293b;">Question No. ${q.number}</span>
                ${statusBadgeText}
            </div>
            ${cleanPrompt ? `<div style="font-size: 16px; line-height: 1.65; color: #0f172a; font-weight: 500; margin-bottom: 14px; white-space: pre-line;">${cleanPrompt}</div>` : ''}
            ${q.gujarati_prompt_path ? `<img src="${q.gujarati_prompt_path}" style="max-width: 100%; display: block; border: 1.5px solid #e2e8f0; border-radius: 8px; padding: 8px; background: #ffffff; margin-bottom: 16px;" alt="Question ${q.number} Gujarati Prompt">` : ''}
            ${optionsHtml}
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 18px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; font-size: 14.5px; font-weight: 600;">
                <span>Your Selection: <strong style="color: ${isCorrect ? '#16a34a' : (isUnattempted ? '#64748b' : '#dc2626')}; font-size: 15px;">${uAns == 5 ? 'Option E (Not Attempted)' : (uAns ? 'Option ' + String.fromCharCode(64 + uAns) : 'None (Unattempted)')}</strong></span>
                <span>Official Answer Key: <strong style="color: #16a34a; font-size: 15px;">${isCancelled ? 'Discrepancy / Cancelled' : (cAns ? 'Option ' + String.fromCharCode(64 + cAns) : 'N/A')}</strong></span>
                <span>Marks Awarded: <strong style="color: ${isCorrect ? '#16a34a' : (isUnattempted ? '#64748b' : '#dc2626')}; font-size: 15px;">${isCorrect ? '+1.00' : (isUnattempted ? '0.00' : '-0.25')}</strong></span>
            </div>
        `;
        reviewContainer.appendChild(card);
    });
}

function backToHome() {
    document.getElementById("resultsScreen").style.display = "none";
    document.getElementById("homeScreen").style.display = "block";
    initExamSelection();
}

function printFullSolution() {
    // 1. Reveal all 100 questions (reset any active filter tab)
    const cards = document.querySelectorAll(".review-card");
    cards.forEach(card => {
        card.style.display = "block";
    });

    const filterBtns = document.querySelectorAll(".filter-tab-btn");
    filterBtns.forEach(b => b.classList.remove("active"));
    const fAll = document.getElementById("filterAllBtn");
    if (fAll) fAll.classList.add("active");

    // 2. Set clean document title for the saved PDF filename
    const prevTitle = document.title;
    const paperName = (latestReviewData && latestReviewData.paper_id) ? latestReviewData.paper_id : (selectedExamId || 'Mock_Exam');
    document.title = `GSSSB_${paperName}_Official_Solution_Paper`;

    // 3. Trigger print / PDF export
    setTimeout(() => {
        window.print();
        setTimeout(() => {
            document.title = prevTitle;
        }, 1000);
    }, 150);
}

// Global hook to guarantee all questions are unhidden if user triggers print via shortcut or browser menu
window.addEventListener('beforeprint', () => {
    const cards = document.querySelectorAll(".review-card");
    cards.forEach(card => {
        card.style.display = "block";
    });
});
