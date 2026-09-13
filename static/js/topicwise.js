/**
 * Topic-wise Question Bank & Study Portal JavaScript
 * GSSSB CCE Class-III (Group-A & Group-B)
 */

(function () {
    'use strict';

    // State
    const state = {
        data: null,
        currentSubjectKey: 'reasoning',
        currentTopicName: '',
        currentMode: 'practice', // 'practice' (default: hidden answers until clicked) or 'study' (all answers visible)
        selectedPaper: 'ALL',
        searchQuery: '',
        currentPage: 1,
        pageSize: 20,
        bookmarks: JSON.parse(localStorage.getItem('tw_bookmarks') || '[]'),
        practiceAnswers: {}, // { qId: selectedOptIndex }
        revealedAnswers: {}, // { qId: boolean }
        zoomImageSrc: ''
    };

    // DOM Elements
    const elements = {
        subjectTabs: document.getElementById('twSubjectTabs'),
        topicsList: document.getElementById('twTopicsList'),
        sidebarCount: document.getElementById('twSidebarCount'),
        activeTopicTitle: document.getElementById('twActiveTopicTitle'),
        activeTopicMeta: document.getElementById('twActiveTopicMeta'),
        questionsStream: document.getElementById('twQuestionsStream'),
        pagination: document.getElementById('twPagination'),
        paperFilter: document.getElementById('twPaperFilter'),
        searchInput: document.getElementById('twSearchInput'),
        modeStudyBtn: document.getElementById('twModeStudy'),
        modePracticeBtn: document.getElementById('twModePractice'),
        bookmarkFilterBtn: document.getElementById('twBookmarkFilterBtn'),
        printBtn: document.getElementById('twPrintBtn'),
        modal: document.getElementById('twZoomModal'),
        modalImg: document.getElementById('twModalImg'),
        modalClose: document.getElementById('twModalClose')
    };

    // Initialize
    async function init() {
        populatePaperFilter();
        setupEventListeners();

        // Load data from window or API
        if (window.topicwiseData) {
            state.data = window.topicwiseData;
            onDataReady();
        } else {
            try {
                const res = await fetch('/api/topicwise/data');
                if (res.ok) {
                    state.data = await res.json();
                    onDataReady();
                } else {
                    showError("Failed to load question bank data.");
                }
            } catch (err) {
                console.error("Error loading data:", err);
                showError("Unable to connect to question database.");
            }
        }
    }

    function populatePaperFilter() {
        if (!elements.paperFilter) return;
        elements.paperFilter.innerHTML = '<option value="ALL">તમામ ૭૧ પેપર્સ (All Papers)</option>';
        for (let i = 1; i <= 71; i++) {
            const opt = document.createElement('option');
            opt.value = `PAPER-${i}`;
            opt.textContent = `Paper-${i}`;
            elements.paperFilter.appendChild(opt);
        }
    }

    function setupEventListeners() {
        // Mode switch
        if (elements.modeStudyBtn && elements.modePracticeBtn) {
            elements.modeStudyBtn.addEventListener('click', () => setMode('study'));
            elements.modePracticeBtn.addEventListener('click', () => setMode('practice'));
        }

        // Paper filter
        if (elements.paperFilter) {
            elements.paperFilter.addEventListener('change', (e) => {
                state.selectedPaper = e.target.value;
                state.currentPage = 1;
                renderQuestions();
            });
        }

        // Search Input
        if (elements.searchInput) {
            let debounceTimer;
            elements.searchInput.addEventListener('input', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    state.searchQuery = e.target.value.trim().toLowerCase();
                    state.currentPage = 1;
                    renderQuestions();
                }, 300);
            });
        }

        // Bookmark Filter Button
        if (elements.bookmarkFilterBtn) {
            elements.bookmarkFilterBtn.addEventListener('click', () => {
                state.currentSubjectKey = 'bookmarks';
                state.currentTopicName = 'Saved Questions (સાચવેલા પ્રશ્નો)';
                state.currentPage = 1;
                updateSubjectTabs();
                renderTopicsSidebar();
                renderQuestions();
            });
        }

        // Print
        if (elements.printBtn) {
            elements.printBtn.addEventListener('click', () => window.print());
        }

        // Modal Close
        if (elements.modalClose) {
            elements.modalClose.addEventListener('click', () => {
                elements.modal.classList.remove('show');
            });
        }
        if (elements.modal) {
            elements.modal.addEventListener('click', (e) => {
                if (e.target === elements.modal) elements.modal.classList.remove('show');
            });
        }
    }

    function onDataReady() {
        renderSubjectTabs();
        selectSubject('reasoning');
    }

    function setMode(mode) {
        state.currentMode = mode;
        if (elements.modeStudyBtn && elements.modePracticeBtn) {
            elements.modeStudyBtn.classList.toggle('active', mode === 'study');
            elements.modePracticeBtn.classList.toggle('active', mode === 'practice');
        }
        renderQuestions();
    }

    function renderSubjectTabs() {
        if (!elements.subjectTabs || !state.data) return;
        elements.subjectTabs.innerHTML = '';

        const subjects = state.data.subjects;
        for (const [sKey, sVal] of Object.entries(subjects)) {
            const btn = document.createElement('button');
            btn.className = `tw-subject-tab ${state.currentSubjectKey === sKey ? 'active' : ''}`;
            btn.innerHTML = `
                <span>${sVal.name}</span>
                <span class="tab-badge">${sVal.marks}M</span>
            `;
            btn.addEventListener('click', () => selectSubject(sKey));
            elements.subjectTabs.appendChild(btn);
        }
    }

    function updateSubjectTabs() {
        if (!elements.subjectTabs) return;
        const tabs = elements.subjectTabs.querySelectorAll('.tw-subject-tab');
        const subjects = Object.keys(state.data.subjects);
        tabs.forEach((tab, index) => {
            const key = subjects[index];
            tab.classList.toggle('active', state.currentSubjectKey === key);
        });
    }

    function selectSubject(sKey) {
        state.currentSubjectKey = sKey;
        updateSubjectTabs();
        renderTopicsSidebar();

        // Select first topic by default
        const subjectObj = state.data.subjects[sKey];
        if (subjectObj && subjectObj.topics) {
            const topicNames = Object.keys(subjectObj.topics);
            if (topicNames.length > 0) {
                selectTopic(topicNames[0]);
            }
        }
    }

    function renderTopicsSidebar() {
        if (!elements.topicsList || !state.data) return;
        elements.topicsList.innerHTML = '';

        if (state.currentSubjectKey === 'bookmarks') {
            elements.sidebarCount.textContent = `${state.bookmarks.length} saved`;
            const item = document.createElement('div');
            item.className = 'tw-topic-item active';
            item.innerHTML = `
                <span class="topic-name"><i class="fa-solid fa-star" style="color: #f59e0b;"></i> સાચવેલા પ્રશ્નો</span>
                <span class="topic-badge">${state.bookmarks.length}</span>
            `;
            elements.topicsList.appendChild(item);
            return;
        }

        const subjectObj = state.data.subjects[state.currentSubjectKey];
        if (!subjectObj) return;

        const topicEntries = Object.entries(subjectObj.topics).sort((a, b) => b[1].length - a[1].length);
        const totalQs = topicEntries.reduce((sum, item) => sum + item[1].length, 0);
        elements.sidebarCount.textContent = `${totalQs} પ્રશ્નો`;

        topicEntries.forEach(([tName, qList]) => {
            const item = document.createElement('div');
            item.className = `tw-topic-item ${state.currentTopicName === tName ? 'active' : ''}`;
            item.innerHTML = `
                <span class="topic-name" title="${tName}">${tName}</span>
                <span class="topic-badge">${qList.length}</span>
            `;
            item.addEventListener('click', () => selectTopic(tName));
            elements.topicsList.appendChild(item);
        });
    }

    function selectTopic(tName) {
        state.currentTopicName = tName;
        state.currentPage = 1;

        // Update active class in sidebar
        const items = elements.topicsList.querySelectorAll('.tw-topic-item');
        items.forEach(item => {
            const nameEl = item.querySelector('.topic-name');
            if (nameEl && nameEl.textContent.trim() === tName.trim()) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        renderQuestions();
    }

    function getFilteredQuestions() {
        if (!state.data) return [];

        let list = [];

        if (state.currentSubjectKey === 'bookmarks') {
            // Collect all bookmarked questions across all subjects
            const bookmarkSet = new Set(state.bookmarks);
            for (const sObj of Object.values(state.data.subjects)) {
                for (const qArray of Object.values(sObj.topics)) {
                    for (const q of qArray) {
                        if (bookmarkSet.has(q.id)) {
                            list.push(q);
                        }
                    }
                }
            }
        } else {
            const subjectObj = state.data.subjects[state.currentSubjectKey];
            if (subjectObj && subjectObj.topics && subjectObj.topics[state.currentTopicName]) {
                list = subjectObj.topics[state.currentTopicName];
            }
        }

        // Apply Paper Filter
        if (state.selectedPaper !== 'ALL') {
            list = list.filter(q => q.paper_id === state.selectedPaper);
        }

        // Apply Search Filter
        if (state.searchQuery) {
            const qLower = state.searchQuery;
            list = list.filter(q => {
                const text = (q.english_prompt || '') + ' ' + (q.qp_code || '') + ' ' + (q.paper_name || '') + ' Q' + q.number;
                return text.toLowerCase().includes(qLower);
            });
        }

        return list;
    }

    function renderQuestions() {
        if (!elements.questionsStream) return;

        const filteredList = getFilteredQuestions();

        // Update Title Header
        elements.activeTopicTitle.innerHTML = `
            <i class="fa-solid fa-folder-open" style="color: var(--primary);"></i>
            ${state.currentTopicName || 'Questions'}
        `;
        elements.activeTopicMeta.textContent = `કુલ ઉપલબ્ધ પ્રશ્નો: ${filteredList.length} (૭૧ પેપર્સમાંથી)`;

        if (filteredList.length === 0) {
            elements.questionsStream.innerHTML = `
                <div style="background: white; border-radius: var(--radius-lg); padding: 3rem; text-align: center; border: 1px dashed var(--border);">
                    <i class="fa-solid fa-file-circle-question" style="font-size: 3rem; color: #94a3b8; margin-bottom: 1rem;"></i>
                    <h3 style="margin: 0 0 0.5rem 0; color: #334155;">કોઈ પ્રશ્નો મળ્યા નથી</h3>
                    <p style="color: #64748b; font-size: 0.9rem; margin: 0;">કૃપા કરીને ફિલ્ટર અથવા સર્ચ ક્વેરી બદલીને ફરી તપાસો.</p>
                </div>
            `;
            elements.pagination.innerHTML = '';
            return;
        }

        // Pagination slice
        const totalPages = Math.ceil(filteredList.length / state.pageSize);
        if (state.currentPage > totalPages) state.currentPage = totalPages;
        if (state.currentPage < 1) state.currentPage = 1;

        const startIndex = (state.currentPage - 1) * state.pageSize;
        const endIndex = startIndex + state.pageSize;
        const pageItems = filteredList.slice(startIndex, endIndex);

        elements.questionsStream.innerHTML = '';

        pageItems.forEach((q, index) => {
            const card = createQuestionCard(q, startIndex + index + 1);
            elements.questionsStream.appendChild(card);
        });

        renderPagination(totalPages);
    }

    function createQuestionCard(q, globalIndex) {
        const card = document.createElement('div');
        card.className = 'tw-question-card';
        card.id = `q_card_${q.id}`;

        const isBookmarked = state.bookmarks.includes(q.id);
        const correctIdx = q.correct_option_index; // 0, 1, 2, 3
        const isAnswerShown = (state.currentMode === 'study') || (state.revealedAnswers[q.id] === true) || (state.practiceAnswers[q.id] !== undefined);
        const userSelected = state.practiceAnswers[q.id];

        // Clean English prompt if contains repetitive headers
        let cleanPromptText = (q.english_prompt || '').trim();
        cleanPromptText = cleanPromptText.replace(/^Yes\s*/i, '');
        cleanPromptText = cleanPromptText.replace(/Quantitative Aptitude Section Id.*$/ms, '');
        cleanPromptText = cleanPromptText.replace(/English Section Id.*$/ms, '');
        cleanPromptText = cleanPromptText.replace(/Question Id : \d+.*$/ms, '');

        // Options HTML
        let optionsHtml = '';
        const optLetters = ['A', 'B', 'C', 'D', 'E'];

        // Helper to resolve asset paths for both local file:// and web server http://
        function resolveAssetUrl(p) {
            if (!p) return '';
            if (p.startsWith('http://') || p.startsWith('https://') || p.startsWith('data:')) {
                return p;
            }
            const clean = p.replace(/^\/+/, '');
            if (window.location.protocol === 'file:') {
                return clean;
            }
            return '/' + clean;
        }

        if (q.options && q.options.length > 0) {
            optionsHtml = q.options.map((opt, oIdx) => {
                const isCorrect = (oIdx === correctIdx);
                const letter = optLetters[oIdx] || `${oIdx + 1}`;
                
                let optClass = 'tw-option-card';
                let badgeHtml = '';

                if (userSelected !== undefined) {
                    if (userSelected === oIdx) {
                        if (isCorrect) {
                            optClass += ' user-selected-correct';
                            badgeHtml = `<span class="tw-correct-badge"><i class="fa-solid fa-circle-check"></i> સાચો જવાબ!</span>`;
                        } else {
                            optClass += ' user-selected-wrong';
                            badgeHtml = `<span class="tw-wrong-badge"><i class="fa-solid fa-circle-xmark"></i> ખોટો જવાબ</span>`;
                        }
                    } else if (isCorrect) {
                        optClass += ' official-correct';
                        badgeHtml = `<span class="tw-correct-badge"><i class="fa-solid fa-circle-check"></i> સાચો જવાબ</span>`;
                    }
                } else if (isAnswerShown) {
                    if (isCorrect) {
                        optClass += ' official-correct';
                        badgeHtml = `<span class="tw-correct-badge"><i class="fa-solid fa-circle-check"></i> સાચો જવાબ</span>`;
                    }
                }

                const optImgUrl = resolveAssetUrl(opt.path);
                const contentHtml = opt.path ? 
                    `<img class="tw-opt-img" src="${optImgUrl}" alt="Option ${letter}" draggable="false">` : 
                    `<span class="tw-opt-text">${opt.text || ''}</span>`;

                return `
                    <div class="${optClass}" data-qid="${q.id}" data-opt-idx="${oIdx}" onclick="window.twSelectOption('${q.id}', ${oIdx}, ${correctIdx})">
                        <div class="tw-opt-letter">${letter}</div>
                        <div class="tw-opt-content">${contentHtml}</div>
                        ${badgeHtml}
                    </div>
                `;
            }).join('');
        }

        // Gujarati Prompt image
        const gujImgUrl = resolveAssetUrl(q.gujarati_prompt_path);
        const gujImgHtml = q.gujarati_prompt_path ? `
            <img class="tw-prompt-img" src="${gujImgUrl}" alt="Question Prompt" onclick="window.twZoomImage('${gujImgUrl}')">
        ` : '';

        // Text prompt
        const textPromptHtml = cleanPromptText ? `
            <div class="tw-prompt-text">${cleanPromptText}</div>
        ` : '';

        // Correct Option Text representation
        const correctLetter = correctIdx >= 0 && correctIdx < optLetters.length ? optLetters[correctIdx] : 'N/A';

        // Footer solution and action button
        const solutionHtml = isAnswerShown ? `
            <div class="tw-solution-text">
                <i class="fa-solid fa-circle-check"></i>
                <span>Official Answer: <strong>Option (${correctLetter})</strong> | QP: ${q.qp_code}</span>
            </div>
            <button type="button" class="tw-toggle-ans-btn active" onclick="window.twToggleShowAnswer('${q.id}')">
                <i class="fa-solid fa-eye-slash"></i> જવાબ છુપાવો
            </button>
        ` : `
            <div class="tw-solution-text" style="display: none;"></div>
            <button type="button" class="tw-toggle-ans-btn" onclick="window.twToggleShowAnswer('${q.id}')">
                <i class="fa-solid fa-eye"></i> સાચો જવાબ જુઓ (Show Answer)
            </button>
        `;

        card.innerHTML = `
            <div class="tw-card-header">
                <div class="tw-meta-badges">
                    <span class="badge-paper"><i class="fa-solid fa-file-lines"></i> ${q.paper_name}</span>
                    <span class="badge-shift"><i class="fa-regular fa-clock"></i> ${q.shift}</span>
                    <span class="badge-date"><i class="fa-regular fa-calendar"></i> ${q.exam_date}</span>
                    <span class="badge-qnum">#Q${q.number}</span>
                </div>
                <div class="tw-card-actions">
                    <button class="tw-icon-btn ${isBookmarked ? 'bookmarked' : ''}" onclick="window.twToggleBookmark('${q.id}')" title="Bookmark / Save">
                        <i class="fa-${isBookmarked ? 'solid' : 'regular'} fa-star"></i>
                    </button>
                    <button class="tw-icon-btn" onclick="window.twCopyLink('${q.id}')" title="Copy Question Link">
                        <i class="fa-solid fa-share-nodes"></i>
                    </button>
                </div>
            </div>

            <div class="tw-prompt-body">
                ${gujImgHtml}
                ${textPromptHtml}
            </div>

            <div class="tw-options-container">
                ${optionsHtml}
            </div>

            <div class="tw-card-footer">
                ${solutionHtml}
            </div>
        `;

        return card;
    }

    function renderPagination(totalPages) {
        if (!elements.pagination) return;
        elements.pagination.innerHTML = '';

        if (totalPages <= 1) return;

        // Prev Button
        const prevBtn = document.createElement('button');
        prevBtn.className = 'tw-page-btn';
        prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
        prevBtn.disabled = state.currentPage === 1;
        prevBtn.addEventListener('click', () => {
            if (state.currentPage > 1) {
                state.currentPage--;
                renderQuestions();
                window.scrollTo({ top: 120, behavior: 'smooth' });
            }
        });
        elements.pagination.appendChild(prevBtn);

        // Page Number Buttons
        let startPage = Math.max(1, state.currentPage - 2);
        let endPage = Math.min(totalPages, startPage + 4);
        if (endPage - startPage < 4) {
            startPage = Math.max(1, endPage - 4);
        }

        for (let p = startPage; p <= endPage; p++) {
            const pageBtn = document.createElement('button');
            pageBtn.className = `tw-page-btn ${p === state.currentPage ? 'active' : ''}`;
            pageBtn.textContent = p;
            pageBtn.addEventListener('click', () => {
                state.currentPage = p;
                renderQuestions();
                window.scrollTo({ top: 120, behavior: 'smooth' });
            });
            elements.pagination.appendChild(pageBtn);
        }

        // Next Button
        const nextBtn = document.createElement('button');
        nextBtn.className = 'tw-page-btn';
        nextBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
        nextBtn.disabled = state.currentPage === totalPages;
        nextBtn.addEventListener('click', () => {
            if (state.currentPage < totalPages) {
                state.currentPage++;
                renderQuestions();
                window.scrollTo({ top: 120, behavior: 'smooth' });
            }
        });
        elements.pagination.appendChild(nextBtn);
    }

    window.twSelectOption = function (qId, selectedIdx, correctIdx) {
        state.practiceAnswers[qId] = selectedIdx;
        renderQuestions();
    };

    window.twToggleShowAnswer = function (qId) {
        state.revealedAnswers[qId] = !state.revealedAnswers[qId];
        renderQuestions();
    };

    window.twToggleBookmark = function (qId) {
        const idx = state.bookmarks.indexOf(qId);
        if (idx >= 0) {
            state.bookmarks.splice(idx, 1);
        } else {
            state.bookmarks.push(qId);
        }
        localStorage.setItem('tw_bookmarks', JSON.stringify(state.bookmarks));
        renderQuestions();
        if (state.currentSubjectKey === 'bookmarks') {
            renderTopicsSidebar();
        }
    };

    window.twZoomImage = function (src) {
        if (!elements.modal || !elements.modalImg) return;
        elements.modalImg.src = src;
        elements.modal.classList.add('show');
    };

    window.twCopyLink = function (qId) {
        const url = `${window.location.origin}/topicwise#${qId}`;
        navigator.clipboard.writeText(url).then(() => {
            alert('Question Link copied to clipboard!');
        }).catch(() => {});
    };

    function showError(msg) {
        if (elements.questionsStream) {
            elements.questionsStream.innerHTML = `
                <div style="background: white; border-radius: var(--radius-lg); padding: 3rem; text-align: center; border: 1px solid #fee2e2;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 2.5rem; color: #ef4444; margin-bottom: 1rem;"></i>
                    <h3 style="margin: 0 0 0.5rem 0; color: #991b1b;">Error</h3>
                    <p style="color: #b91c1c; font-size: 0.95rem;">${msg}</p>
                </div>
            `;
        }
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
