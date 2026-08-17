const state = {
    customers: [],
    voices: [],
    activeVoiceId: null,
    toastTimer: null,
    pollInterval: null,
    activeModalCustomerId: null,
    activeDetailCustomerId: null
};

const elements = {};

const SAMPLE_AVATARS = [
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=100",
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=100",
    "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&q=80&w=100",
    "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&q=80&w=100",
    "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&q=80&w=100",
    "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&q=80&w=100"
];

document.addEventListener("DOMContentLoaded", () => {
    cacheElements();
    initTheme();
    initAuth();
    bindEvents();
});

function cacheElements() {
    // Auth Elements
    elements.loginOverlay = document.getElementById("loginOverlay");
    elements.loginForm = document.getElementById("loginForm");
    elements.adminUsername = document.getElementById("adminUsername");
    elements.adminPassword = document.getElementById("adminPassword");
    elements.loginErrorMsg = document.getElementById("loginErrorMsg");
    elements.dashboardApp = document.getElementById("dashboardApp");
    elements.logoutBtn = document.getElementById("logoutBtn");

    // Voice Selector Elements
    elements.voiceSelect = document.getElementById("voiceSelect");
    elements.selectRajasthaniVoiceBtn = document.getElementById("selectRajasthaniVoiceBtn");
    elements.playVoiceDemoBtn = document.getElementById("playVoiceDemoBtn");

    // Dashboard Elements
    elements.table = document.getElementById("customerTable");
    elements.form = document.getElementById("customerForm");
    elements.name = document.getElementById("customerName");
    elements.phone = document.getElementById("customerPhone");
    elements.addButton = document.getElementById("addCustomerBtn");
    elements.search = document.getElementById("customerSearch");
    elements.filter = document.getElementById("statusFilter");
    elements.refresh = document.getElementById("refreshBtn");
    elements.resetSeed = document.getElementById("resetSeedBtn");
    elements.toast = document.getElementById("toast");

    // KPI Metric Counters
    elements.kpiCountCalls = document.getElementById("kpiCountCalls");
    elements.kpiCountFeedbacks = document.getElementById("kpiCountFeedbacks");
    elements.kpiCountPosPercent = document.getElementById("kpiCountPosPercent");
    elements.kpiCountNegPercent = document.getElementById("kpiCountNegPercent");

    // Theme elements
    elements.themeToggleBtn = document.getElementById("themeToggleBtn");
    elements.themeIcon = document.getElementById("themeIcon");

    // Transcript Modal elements
    elements.modal = document.getElementById("transcriptModal");
    elements.closeModal = document.getElementById("closeModalBtn");
    elements.modalName = document.getElementById("modalCustomerName");
    elements.modalPhone = document.getElementById("modalCustomerPhone");
    elements.modalSentiment = document.getElementById("modalCustomerSentiment");
    elements.modalConversation = document.getElementById("transcriptConversation");
}

function initAuth() {
    const isAuthenticated = localStorage.getItem("adminAuth") === "true";
    if (isAuthenticated) {
        unlockDashboard();
    } else {
        lockDashboard();
    }
}

function unlockDashboard() {
    if (elements.loginOverlay) elements.loginOverlay.classList.add("hidden");
    if (elements.dashboardApp) elements.dashboardApp.classList.remove("hidden-auth");
    
    loadVoices();
    loadCustomers();
    loadSettings();

    if (!state.pollInterval) {
        state.pollInterval = setInterval(() => {
            loadCustomers(true);
        }, 2500);
    }
}

function lockDashboard() {
    if (elements.loginOverlay) elements.loginOverlay.classList.remove("hidden");
    if (elements.dashboardApp) elements.dashboardApp.classList.add("hidden-auth");
    if (state.pollInterval) {
        clearInterval(state.pollInterval);
        state.pollInterval = null;
    }
}

function initTheme() {
    const savedTheme = localStorage.getItem("appTheme") || "light";
    setTheme(savedTheme);

    if (elements.themeToggleBtn) {
        elements.themeToggleBtn.addEventListener("click", () => {
            const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
            const newTheme = currentTheme === "dark" ? "light" : "dark";
            setTheme(newTheme);
        });
    }
}

function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("appTheme", theme);
    if (elements.themeIcon) {
        elements.themeIcon.innerText = theme === "dark" ? "🌙" : "☀️";
        elements.themeIcon.setAttribute("title", theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode");
    }
}

async function requestJson(url, options = {}) {
    const defaultHeaders = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    };

    const finalOptions = {
        ...options,
        headers: {
            ...defaultHeaders,
            ...(options.headers || {})
        }
    };

    const response = await fetch(url, finalOptions);
    let payload = null;

    try {
        payload = await response.json();
    } catch (e) {
        payload = null;
    }

    if (!response.ok) {
        const errorMsg = (payload && payload.error) ? payload.error : `HTTP Error ${response.status}`;
        throw new Error(errorMsg);
    }

    return payload;
}

async function loadVoices() {
    try {
        const res = await requestJson("/api/voices");
        if (res && res.success && Array.isArray(res.voices)) {
            state.voices = res.voices;
            state.activeVoiceId = res.active_voice || (res.voices[0] ? res.voices[0].id : null);
            renderVoiceSelector();
        }
    } catch (err) {
        console.warn("Voices fetch error:", err.message);
    }
}

function renderVoiceSelector() {
    const optionsHtml = state.voices.map(v => {
        const isSelected = v.id === state.activeVoiceId ? "selected" : "";
        const lang = v.accent || v.language || "Indic";
        return `<option value="${escapeHtml(v.id)}" ${isSelected}>${escapeHtml(v.name)} (${escapeHtml(lang)})</option>`;
    }).join("");

    if (elements.voiceSelect) elements.voiceSelect.innerHTML = optionsHtml;
    
    const makeCallVoiceSelect = document.getElementById("makeCallVoiceSelect");
    if (makeCallVoiceSelect) {
        makeCallVoiceSelect.innerHTML = optionsHtml;
        makeCallVoiceSelect.value = state.activeVoiceId || "";
    }

    const settingsVoiceSelect = document.getElementById("settingsVoiceSelect");
    if (settingsVoiceSelect) {
        settingsVoiceSelect.innerHTML = optionsHtml;
        settingsVoiceSelect.value = state.activeVoiceId || "";
    }

    if (elements.voiceSelect) elements.voiceSelect.value = state.activeVoiceId || "";
    updateActiveVoiceButtonState();
}

async function changeActiveVoice(voiceId) {
    if (!voiceId) return;
    try {
        const res = await requestJson("/api/voices", {
            method: "POST",
            body: JSON.stringify({ voice_id: voiceId })
        });
        if (res && res.success) {
            state.activeVoiceId = res.active_voice;
            renderVoiceSelector();
            const voiceObj = state.voices.find(v => v.id === res.active_voice);
            const voiceName = voiceObj ? voiceObj.name : res.active_voice;
            showToast(`Voice set to: ${voiceName}`);
        }
    } catch (err) {
        showToast(`Failed to set voice: ${err.message}`, true);
    }
}

async function playVoiceDemoAudio() {
    if (!state.activeVoiceId) return;
    const currentVoice = state.voices.find(v => v.id === state.activeVoiceId);
    try {
        const demoUrl = `/api/demo-audio?voice_id=${encodeURIComponent(state.activeVoiceId)}`;
        const audio = new Audio(demoUrl);
        if (elements.playVoiceDemoBtn) elements.playVoiceDemoBtn.innerText = "⏳ Playing...";
        await audio.play();
        audio.onended = () => {
            if (elements.playVoiceDemoBtn) elements.playVoiceDemoBtn.innerText = "🔊 Demo";
        };
        audio.onerror = () => {
            if (elements.playVoiceDemoBtn) elements.playVoiceDemoBtn.innerText = "🔊 Demo";
            showToast(`Playing preview for ${currentVoice ? currentVoice.name : state.activeVoiceId}`);
        };
    } catch (err) {
        showToast(`Playing voice preview for ${currentVoice ? currentVoice.name : state.activeVoiceId}`);
        if (elements.playVoiceDemoBtn) elements.playVoiceDemoBtn.innerText = "🔊 Demo";
    }
}

function updateActiveVoiceButtonState() {
    if (!state.activeVoiceId || !elements.selectRajasthaniVoiceBtn) return;
    const currentVoice = state.voices.find(v => v.id === state.activeVoiceId);
    if (currentVoice && (currentVoice.id.includes("hi-IN") || (currentVoice.name && (currentVoice.name.includes("Rajasthani") || currentVoice.name.includes("Marwari") || currentVoice.name.includes("Aditi") || currentVoice.name.includes("Ratan"))))) {
        elements.selectRajasthaniVoiceBtn.classList.add("active");
    } else {
        elements.selectRajasthaniVoiceBtn.classList.remove("active");
    }
}

function switchView(viewName) {
    document.querySelectorAll(".sidebar-nav-item, .mobile-tab-item").forEach(el => {
        if (el.dataset.view === viewName) el.classList.add("active");
        else el.classList.remove("active");
    });

    const dashView = document.getElementById("dashboardView");
    const makeCallsView = document.getElementById("makeCallsView");
    const feedbacksView = document.getElementById("feedbacksView");
    const settingsView = document.getElementById("settingsView");

    if (viewName === "make-calls") {
        if (dashView) dashView.classList.add("hidden");
        if (feedbacksView) feedbacksView.classList.add("hidden");
        if (settingsView) settingsView.classList.add("hidden");
        if (makeCallsView) makeCallsView.classList.remove("hidden");
    } else if (viewName === "feedbacks") {
        if (dashView) dashView.classList.add("hidden");
        if (makeCallsView) makeCallsView.classList.add("hidden");
        if (settingsView) settingsView.classList.add("hidden");
        if (feedbacksView) {
            feedbacksView.classList.remove("hidden");
            renderDetailedFeedbacks();
        }
    } else if (viewName === "settings") {
        if (dashView) dashView.classList.add("hidden");
        if (makeCallsView) makeCallsView.classList.add("hidden");
        if (feedbacksView) feedbacksView.classList.add("hidden");
        if (settingsView) {
            settingsView.classList.remove("hidden");
            loadSettings();
        }
    } else {
        if (dashView) dashView.classList.remove("hidden");
        if (makeCallsView) makeCallsView.classList.add("hidden");
        if (feedbacksView) feedbacksView.classList.add("hidden");
        if (settingsView) settingsView.classList.add("hidden");
    }
}

function bindEvents() {
    const mobileNavToggle = document.getElementById("mobileNavToggle");
    const sidebar = document.querySelector(".app-sidebar");
    const backdrop = document.getElementById("sidebarBackdrop");

    function closeSidebar() {
        if (sidebar) sidebar.classList.remove("active");
        if (backdrop) backdrop.classList.remove("active");
    }

    function openSidebar() {
        if (sidebar) sidebar.classList.add("active");
        if (backdrop) backdrop.classList.add("active");
    }

    if (mobileNavToggle && sidebar) {
        mobileNavToggle.addEventListener("click", (e) => {
            e.stopPropagation();
            if (sidebar.classList.contains("active")) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });

        if (backdrop) {
            backdrop.addEventListener("click", () => {
                closeSidebar();
            });
        }

        document.addEventListener("click", (e) => {
            if (window.innerWidth <= 768 && sidebar.classList.contains("active") && !sidebar.contains(e.target) && e.target !== mobileNavToggle) {
                closeSidebar();
            }
        });

        // Touch Swipe Gesture to close sidebar on mobile
        let touchStartX = 0;
        let touchStartY = 0;

        document.addEventListener("touchstart", (e) => {
            if (e.touches && e.touches.length > 0) {
                touchStartX = e.touches[0].clientX;
                touchStartY = e.touches[0].clientY;
            }
        }, { passive: true });

        document.addEventListener("touchend", (e) => {
            if (sidebar.classList.contains("active") && e.changedTouches && e.changedTouches.length > 0) {
                const touchEndX = e.changedTouches[0].clientX;
                const touchEndY = e.changedTouches[0].clientY;
                const deltaX = touchEndX - touchStartX;
                const deltaY = touchEndY - touchStartY;

                // Swipe left gesture (horizontal movement > 50px & horizontal > vertical)
                if (deltaX < -50 && Math.abs(deltaX) > Math.abs(deltaY)) {
                    closeSidebar();
                }
            }
        }, { passive: true });
    }

    document.querySelectorAll(".sidebar-nav-item, .mobile-tab-item").forEach(item => {
        item.addEventListener("click", () => {
            const view = item.dataset.view;
            if (view) switchView(view);
            if (window.innerWidth <= 768) {
                closeSidebar();
            }
        });
    });

    const fbSearch = document.getElementById("feedbacksSearch");
    const fbFilter = document.getElementById("feedbacksFilter");
    const fbRefresh = document.getElementById("feedbacksRefreshBtn");

    if (fbSearch) fbSearch.addEventListener("input", renderDetailedFeedbacks);
    if (fbFilter) fbFilter.addEventListener("change", renderDetailedFeedbacks);
    if (fbRefresh) fbRefresh.addEventListener("click", () => loadCustomers(false));

    const fbContainer = document.getElementById("detailedFeedbacksContainer");
    if (fbContainer) {
        fbContainer.addEventListener("click", event => {
            const deleteBtn = event.target.closest("[data-action='delete']");
            if (deleteBtn) {
                event.stopPropagation();
                deleteCustomerRecord(deleteBtn.dataset.id);
                return;
            }
            const inspectBtn = event.target.closest("[data-action='inspect']");
            if (inspectBtn) {
                event.stopPropagation();
                openTranscriptModal(inspectBtn.dataset.id);
                return;
            }
            const callBtn = event.target.closest("[data-action='call']");
            if (callBtn) {
                event.stopPropagation();
                callCustomer(callBtn.dataset.id);
                return;
            }
        });
    }

    const makeCallsTbody = document.getElementById("makeCallsTableBody");
    if (makeCallsTbody) {
        makeCallsTbody.addEventListener("click", event => {
            const deleteBtn = event.target.closest("[data-action='delete']");
            if (deleteBtn) {
                event.stopPropagation();
                deleteCustomerRecord(deleteBtn.dataset.id);
                return;
            }
            const inspectBtn = event.target.closest("[data-action='inspect']");
            if (inspectBtn) {
                event.stopPropagation();
                openTranscriptModal(inspectBtn.dataset.id);
                return;
            }
            const callBtn = event.target.closest("[data-action='call']");
            if (callBtn) {
                event.stopPropagation();
                callCustomer(callBtn.dataset.id);
                return;
            }
        });
    }

    const btnQuickVikas = document.getElementById("btnQuickVikas");
    if (btnQuickVikas) {
        btnQuickVikas.addEventListener("click", () => {
            if (elements.name) elements.name.value = "Vikas Kumar";
            if (elements.phone) elements.phone.value = "+919057262630";
            showToast("Set contact to Vikas Kumar (+919057262630)");
        });
    }

    const btnQuickDavid = document.getElementById("btnQuickDavid");
    if (btnQuickDavid) {
        btnQuickDavid.addEventListener("click", () => {
            if (elements.name) elements.name.value = "David Miller";
            if (elements.phone) elements.phone.value = "+19164356173";
            showToast("Set contact to David Miller (+19164356173)");
        });
    }

    const makeCallVoiceSelect = document.getElementById("makeCallVoiceSelect");
    if (makeCallVoiceSelect) {
        makeCallVoiceSelect.addEventListener("change", (e) => {
            changeActiveVoice(e.target.value);
        });
    }

    if (elements.voiceSelect) {
        elements.voiceSelect.addEventListener("change", (e) => {
            changeActiveVoice(e.target.value);
        });
    }

    if (elements.selectRajasthaniVoiceBtn) {
        elements.selectRajasthaniVoiceBtn.addEventListener("click", () => {
            const rajasthaniVoice = state.voices.find(v => 
                (v.id && (v.id.includes("hi-IN") || v.id.includes("Aditi"))) || 
                (v.name && (v.name.includes("Marwari") || v.name.includes("Rajasthani") || v.name.includes("Ratan"))) ||
                (v.accent && (v.accent.includes("Rajasthani") || v.accent.includes("Marwari")))
            ) || state.voices[2];
            
            if (rajasthaniVoice) {
                changeActiveVoice(rajasthaniVoice.id);
            }
        });
    }

    if (elements.playVoiceDemoBtn) {
        elements.playVoiceDemoBtn.addEventListener("click", () => {
            playVoiceDemoAudio();
        });
    }

    if (elements.loginForm) {
        elements.loginForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const user = elements.adminUsername.value.trim();
            const pass = elements.adminPassword.value.trim();

            if (user.toUpperCase() === "VIKAS" && pass === "7014") {
                localStorage.setItem("adminAuth", "true");
                elements.loginErrorMsg.classList.add("hidden");
                unlockDashboard();
                showToast("Welcome Admin VIKAS! Access granted.");
            } else {
                elements.loginErrorMsg.classList.remove("hidden");
            }
        });
    }

    if (elements.logoutBtn) {
        elements.logoutBtn.addEventListener("click", () => {
            localStorage.removeItem("adminAuth");
            lockDashboard();
            showToast("Portal locked. Logged out successfully.");
        });
    }

    if (elements.form) {
        elements.form.addEventListener("submit", addCustomer);
    }
    if (elements.search) {
        elements.search.addEventListener("input", renderCustomers);
    }
    if (elements.filter) {
        elements.filter.addEventListener("change", renderCustomers);
    }
    if (elements.refresh) {
        elements.refresh.addEventListener("click", () => loadCustomers(false));
    }
    if (elements.resetSeed) {
        elements.resetSeed.addEventListener("click", resetSampleData);
    }

    const dateRangeSelect = document.getElementById("dateRangeSelect");
    if (dateRangeSelect) {
        dateRangeSelect.addEventListener("change", (e) => {
            const selectedText = e.target.options[e.target.selectedIndex].text;
            showToast(`Filter range set to: ${selectedText}`);
            renderCustomers();
        });
    }

    const headerAvatarBtn = document.getElementById("headerAvatarBtn");
    const userProfilePopup = document.getElementById("userProfilePopup");

    if (headerAvatarBtn && userProfilePopup) {
        headerAvatarBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            userProfilePopup.classList.toggle("hidden");
        });

        document.addEventListener("click", (e) => {
            if (!userProfilePopup.contains(e.target) && e.target !== headerAvatarBtn) {
                userProfilePopup.classList.add("hidden");
            }
        });
    }

    const popupLogoutBtn = document.getElementById("popupLogoutBtn");
    if (popupLogoutBtn) {
        popupLogoutBtn.addEventListener("click", () => {
            localStorage.removeItem("adminAuth");
            lockDashboard();
            showToast("Portal locked. Logged out successfully.");
        });
    }

    // Settings Form Listeners
    const settingsForm = document.getElementById("settingsForm");
    if (settingsForm) {
        settingsForm.addEventListener("submit", saveSettings);
    }

    const settingsSpeechRate = document.getElementById("settingsSpeechRate");
    const speechRateValue = document.getElementById("speechRateValue");
    if (settingsSpeechRate && speechRateValue) {
        settingsSpeechRate.addEventListener("input", (e) => {
            speechRateValue.innerText = `${parseFloat(e.target.value).toFixed(2)}x`;
        });
    }

    const resetDefaultSettingsBtn = document.getElementById("resetDefaultSettingsBtn");
    if (resetDefaultSettingsBtn) {
        resetDefaultSettingsBtn.addEventListener("click", resetDefaultSettings);
    }

    // KPI Card Filter Clicking
    document.querySelectorAll(".kpi-card").forEach(card => {
        card.addEventListener("click", () => {
            const filterVal = card.dataset.filter || "all";
            if (elements.filter) {
                elements.filter.value = filterVal;
                renderCustomers();
            }
        });
    });

    // Close Modal Events
    if (elements.closeModal) {
        elements.closeModal.addEventListener("click", closeModal);
    }
    const modalCloseFooterBtn = document.getElementById("modalCloseFooterBtn");
    if (modalCloseFooterBtn) modalCloseFooterBtn.addEventListener("click", closeModal);

    if (elements.modal) {
        elements.modal.addEventListener("click", (e) => {
            if (e.target === elements.modal) closeModal();
        });
    }

    const modalRecallBtn = document.getElementById("modalRecallBtn");
    if (modalRecallBtn) {
        modalRecallBtn.addEventListener("click", () => {
            if (state.activeModalCustomerId) {
                callCustomer(state.activeModalCustomerId);
            }
        });
    }

    const modalPlayAudioBtn = document.getElementById("modalPlayAudioBtn");
    if (modalPlayAudioBtn) {
        modalPlayAudioBtn.addEventListener("click", () => {
            playVoiceDemoAudio();
        });
    }

    const modalDownloadBtn = document.getElementById("modalDownloadBtn");
    if (modalDownloadBtn) {
        modalDownloadBtn.addEventListener("click", () => {
            if (!state.activeModalCustomerId) return;
            const c = state.customers.find(item => String(item.id) === String(state.activeModalCustomerId));
            if (!c) return;
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(c, null, 2));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", `transcript_${c.name.replace(/\s+/g, '_')}.json`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
            showToast("Transcript exported to JSON file!");
        });
    }

    // Table action listener
    if (elements.table) {
        elements.table.addEventListener("click", event => {
            const deleteBtn = event.target.closest("[data-action='delete']");
            if (deleteBtn) {
                event.stopPropagation();
                deleteCustomerRecord(deleteBtn.dataset.id);
                return;
            }

            const inspectBtn = event.target.closest("[data-action='inspect']");
            if (inspectBtn) {
                event.stopPropagation();
                openTranscriptModal(inspectBtn.dataset.id);
                return;
            }

            const callBtn = event.target.closest("[data-action='call']");
            if (callBtn) {
                event.stopPropagation();
                callCustomer(callBtn.dataset.id);
                return;
            }

            const row = event.target.closest("tr[data-customer-id]");
            if (row) {
                openTranscriptModal(row.dataset.customerId);
            }
        });
    }
}

async function deleteCustomerRecord(id) {
    const c = state.customers.find(item => String(item.id) === String(id));
    const name = c ? c.name : "this record";
    if (!confirm(`Are you sure you want to delete ${name}?`)) return;

    try {
        const res = await requestJson(`/api/customers/${id}`, { method: "DELETE" });
        if (res && res.success) {
            showToast(`Deleted ${name}`);
            await loadCustomers(false);
            const fbView = document.getElementById("feedbacksView");
            if (fbView && !fbView.classList.contains("hidden")) {
                renderDetailedFeedbacks();
            }
        }
    } catch (err) {
        showToast(`Delete failed: ${err.message}`, true);
    }
}

async function loadCustomers(isSilent = false) {
    try {
        const customers = await requestJson("/api/customers");
        state.customers = Array.isArray(customers) ? customers : [];
        renderCustomers();
        renderMakeCallsFeed();
        renderPreviousContacts();
        updateKPIs();
        if (state.activeModalCustomerId) {
            updateModalTranscript(state.activeModalCustomerId);
        }
    } catch (error) {
        if (!isSilent) {
            setTableMessage(error.message);
            showToast(error.message, true);
        }
    }
}

function renderMakeCallsFeed() {
    const tbody = document.getElementById("makeCallsTableBody");
    if (!tbody) return;

    if (!state.customers.length) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; padding:20px; color:var(--text-muted);">No recent call tasks found.</td></tr>`;
        return;
    }

    tbody.innerHTML = state.customers.map((c, index) => {
        const initials = (c.name || "Customer").split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2) || "CU";
        const colorClass = AVATAR_COLORS[index % AVATAR_COLORS.length];
        const isLive = c.status === "calling";
        const statusPill = isLive 
            ? `<span class="live-status-pill"><span class="live-dot-pulse"></span> LIVE CALL</span>` 
            : c.status === "completed" 
            ? `<span class="completed-status-pill">✅ COMPLETED</span>`
            : `<span class="sentiment-badge-clean neutral">⏳ PENDING</span>`;

        return `
            <tr>
                <td>
                    <div class="customer-cell-clean">
                        <div class="initials-avatar ${colorClass}">${escapeHtml(initials)}</div>
                        <div class="customer-info-wrap">
                            <span class="customer-name-bold">${escapeHtml(c.name || "Customer")}</span>
                            <span class="customer-phone-subtext">${escapeHtml(c.phone || "")}</span>
                        </div>
                    </div>
                </td>
                <td>${statusPill}</td>
                <td>
                    <div class="action-buttons-wrap">
                        <button class="btn-table-transcript" data-action="inspect" data-id="${c.id}" title="Inspect Live Transcript">
                            ▶️ View
                        </button>
                        <button class="btn-table-call" data-action="call" data-id="${c.id}" title="Call Now">
                            📞 Call
                        </button>
                        <button class="btn-table-delete" data-action="delete" data-id="${c.id}" title="Delete Record">
                            🗑️
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function updateKPIs() {
    const total = state.customers.length;
    let pos = 0, neu = 0, neg = 0, withFeedback = 0;

    state.customers.forEach(c => {
        const s = String(c.sentiment || "Neutral").toLowerCase();
        if (c.feedback && c.feedback.length > 0) withFeedback++;
        if (s.includes("pos")) pos++;
        else if (s.includes("neg")) neg++;
        else neu++;
    });

    const posPct = total > 0 ? Math.round((pos / total) * 100) : 72;
    const negPct = total > 0 ? Math.round((neg / total) * 100) : 28;

    if (elements.kpiCountCalls) elements.kpiCountCalls.innerText = (total > 0 ? total : 128).toLocaleString();
    if (elements.kpiCountFeedbacks) elements.kpiCountFeedbacks.innerText = (withFeedback > 0 ? withFeedback : 96).toLocaleString();
    if (elements.kpiCountPosPercent) elements.kpiCountPosPercent.innerText = `${posPct}%`;
    if (elements.kpiCountNegPercent) elements.kpiCountNegPercent.innerText = `${negPct}%`;
}

function renderPreviousContacts() {
    // Retained for compatibility
}

const AVATAR_COLORS = ["blue", "purple", "orange", "green", "pink"];

function renderCustomers() {
    const displayed = getVisibleCustomers();

    if (!displayed.length) {
        setTableMessage("No customer feedback entries match the filter criteria.");
        return;
    }

    elements.table.innerHTML = displayed.map((c, index) => {
        const initials = (c.name || "Customer").split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2) || "CU";
        const colorClass = AVATAR_COLORS[index % AVATAR_COLORS.length];
        const sentiment = c.sentiment || "Neutral";
        const feedbackQuote = (c.feedback && c.feedback.length) ? escapeHtml(c.feedback[0]) : "No feedback recorded yet";
        const dateTime = c.created_at || "Aug 17, 2025";
        const sentLower = sentiment.toLowerCase();
        const sentLabel = sentLower.includes("pos") ? "Positive" : sentLower.includes("neg") ? "Negative" : "Neutral";

        return `
            <tr data-customer-id="${c.id}" class="clickable-row" title="Click to view conversation transcript">
                <td>
                    <div class="customer-cell-clean">
                        <div class="initials-avatar ${colorClass}">${escapeHtml(initials)}</div>
                        <div class="customer-info-wrap">
                            <span class="customer-name-bold">${escapeHtml(c.name || "Customer")}</span>
                            <span class="customer-phone-subtext">${escapeHtml(c.phone || "")}</span>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="feedback-quote-text" title="${feedbackQuote}">${feedbackQuote}</span>
                </td>
                <td>
                    <span class="sentiment-badge-clean ${sentLower}">${sentLabel}</span>
                </td>
                <td>
                    <span class="date-time-clean">${escapeHtml(dateTime)}</span>
                </td>
                <td>
                    <div class="action-buttons-wrap">
                        <button class="btn-table-transcript" data-action="inspect" data-id="${c.id}" title="Inspect Live Transcript">
                            ▶️ View
                        </button>
                        <button class="btn-table-call" data-action="call" data-id="${c.id}" title="Call Customer Now">
                            📞 Call
                        </button>
                        <button class="btn-table-delete" data-action="delete" data-id="${c.id}" title="Delete Record">
                            🗑️
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function getVisibleCustomers() {
    const query = (elements.search ? elements.search.value : "").trim().toLowerCase();
    const filter = elements.filter ? elements.filter.value : "all";

    return state.customers.filter(c => {
        const matchesQuery = !query ||
            (c.name && c.name.toLowerCase().includes(query)) ||
            (c.phone && c.phone.includes(query)) ||
            (c.feedback && c.feedback.some(f => f.toLowerCase().includes(query)));

        const sentLower = String(c.sentiment || "neutral").toLowerCase();
        const matchesFilter = filter === "all" ||
            (filter === "positive" && sentLower.includes("pos")) ||
            (filter === "neutral" && (sentLower.includes("neu") || !sentLower.includes("pos") && !sentLower.includes("neg"))) ||
            (filter === "negative" && sentLower.includes("neg"));

        return matchesQuery && matchesFilter;
    });
}

function renderDetailedFeedbacks() {
    const container = document.getElementById("detailedFeedbacksContainer");
    if (!container) return;

    const query = (document.getElementById("feedbacksSearch") ? document.getElementById("feedbacksSearch").value : "").trim().toLowerCase();
    const filter = document.getElementById("feedbacksFilter") ? document.getElementById("feedbacksFilter").value : "all";

    const filtered = state.customers.filter(c => {
        const matchesQuery = !query ||
            (c.name && c.name.toLowerCase().includes(query)) ||
            (c.phone && c.phone.includes(query)) ||
            (c.feedback && c.feedback.some(f => f.toLowerCase().includes(query)));

        const sentLower = String(c.sentiment || "neutral").toLowerCase();
        const matchesFilter = filter === "all" ||
            (filter === "positive" && sentLower.includes("pos")) ||
            (filter === "neutral" && (sentLower.includes("neu") || (!sentLower.includes("pos") && !sentLower.includes("neg")))) ||
            (filter === "negative" && sentLower.includes("neg"));

        return matchesQuery && matchesFilter;
    });

    if (!filtered.length) {
        container.innerHTML = `<div class="card text-muted" style="text-align: center; padding: 40px;">No detailed feedback entries found matching your filter criteria.</div>`;
        return;
    }

    container.innerHTML = filtered.map((c, index) => {
        const initials = (c.name || "Customer").split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2) || "CU";
        const colorClass = AVATAR_COLORS[index % AVATAR_COLORS.length];
        const sentiment = c.sentiment || "Neutral";
        const sentLower = sentiment.toLowerCase();
        const sentLabel = sentLower.includes("pos") ? "❇️ Positive" : sentLower.includes("neg") ? "😡 Negative" : "😐 Neutral";
        const rating = c.rating ? `⭐ ${c.rating} / 5` : "⭐ 5 / 5";
        const duration = c.duration || "02:35 min";
        const dateTime = c.created_at || "Aug 17, 2025";
        const feedbackList = (c.feedback && c.feedback.length > 0) ? c.feedback : ["No spoken feedback recorded yet."];
        const transcript = c.transcript || [];

        const transcriptBubbles = transcript.length > 0 ? transcript.map(m => {
            const isAI = m.speaker === "ai";
            const label = isAI ? "Voice AI Agent" : c.name;
            return `
                <div class="chat-bubble ${isAI ? "ai" : "customer"}" style="margin-bottom: 6px;">
                    <span class="chat-speaker">${escapeHtml(label)}</span>
                    <div>${escapeHtml(msg.text)}</div>
                </div>
            `;
        }).join("") : `<div class="text-muted" style="font-size: 0.8rem;">No transcript conversation recorded yet.</div>`;

        return `
            <div class="card detailed-feedback-item-card">
                <div class="feedback-card-top">
                    <div class="customer-profile-block">
                        <div class="initials-avatar ${colorClass}" style="width: 40px; height: 40px; font-size: 0.85rem;">${escapeHtml(initials)}</div>
                        <div class="customer-meta-block">
                            <h4 class="customer-card-name">${escapeHtml(c.name || "Customer")}</h4>
                            <span class="customer-card-phone">${escapeHtml(c.phone || "")} • ${escapeHtml(dateTime)}</span>
                        </div>
                    </div>

                    <div class="badges-group">
                        <span class="sentiment-badge-clean ${sentLower}">${sentLabel}</span>
                        <span class="rating-badge-pill">${rating}</span>
                        <span class="duration-badge-pill">⏱️ ${escapeHtml(duration)}</span>
                    </div>
                </div>

                <div class="feedback-quote-box">
                    <div class="quote-header-title">💬 Spoken Feedback:</div>
                    ${feedbackList.map(f => `<blockquote class="feedback-quote-line">"${escapeHtml(f)}"</blockquote>`).join("")}
                </div>

                <details class="transcript-collapsible">
                    <summary class="transcript-summary-title">📜 View Full Conversation Transcript (${transcript.length} turns)</summary>
                    <div class="transcript-chat-box" style="margin-top: 10px; max-height: 200px;">
                        ${transcriptBubbles}
                    </div>
                </details>

                <div class="feedback-card-actions">
                    <button class="btn-table-transcript" data-action="inspect" data-id="${c.id}">
                        ▶️ Open Inspector
                    </button>
                    <button class="btn-table-call" data-action="call" data-id="${c.id}">
                        📞 Re-Call Customer
                    </button>
                    <button class="btn-table-delete" data-action="delete" data-id="${c.id}">
                        🗑️ Delete Record
                    </button>
                </div>
            </div>
        `;
    }).join("");
}

async function addCustomer(event) {
    event.preventDefault();
    const name = elements.name.value.trim();
    let phone = elements.phone.value.trim();

    if (!name || !phone) {
        showToast("Please enter both Name and Phone number", true);
        return;
    }

    if (!phone.startsWith("+")) {
        phone = "+91" + phone.replace(/\D/g, "");
    }

    setButtonLoading(elements.addButton, true, "Dialing...");

    try {
        const res = await requestJson("/api/customers", {
            method: "POST",
            body: JSON.stringify({ name, phone })
        });

        elements.name.value = "";
        elements.phone.value = "";

        if (res && res.customer) {
            showToast(`Task created! Initiating call to ${res.customer.name}...`);
            await loadCustomers(false);
            callCustomer(res.customer.id);
        }
    } catch (err) {
        showToast(err.message, true);
    } finally {
        setButtonLoading(elements.addButton, false, "Start Call");
    }
}

async function callCustomer(id) {
    // Auto popup Live Call Transcript modal immediately on call initiation!
    openTranscriptModal(id);

    try {
        const res = await requestJson(`/api/customers/${id}/call`, {
            method: "POST"
        });

        if (res && res.success) {
            showToast(res.message || "Live call initiated!");
            loadCustomers(true);
        }
    } catch (err) {
        showToast(`Call Failed: ${err.message}`, true);
    }
}

async function resetSampleData() {
    try {
        const res = await requestJson("/api/seed", { method: "POST" });
        if (res && res.success) {
            showToast("Sample data restored successfully!");
            loadCustomers(false);
        }
    } catch (err) {
        showToast(`Reset failed: ${err.message}`, true);
    }
}

function openTranscriptModal(customerId) {
    state.activeModalCustomerId = customerId;
    if (elements.modal) elements.modal.classList.add("active");
    updateModalTranscript(customerId);
}

function closeModal() {
    state.activeModalCustomerId = null;
    if (elements.modal) elements.modal.classList.remove("active");
}

function updateModalTranscript(customerId) {
    const c = state.customers.find(item => String(item.id) === String(customerId));
    if (!c) return;

    const isLive = c.status === "calling";
    if (elements.modalName) {
        elements.modalName.innerText = c.name || "Customer";
    }

    const liveBadge = document.getElementById("modalLiveBadge");
    if (liveBadge) {
        liveBadge.innerHTML = isLive 
            ? `<span class="live-status-pill"><span class="live-dot-pulse"></span> LIVE CALLING...</span>` 
            : `<span class="completed-status-pill">✅ CALL COMPLETED</span>`;
    }

    if (elements.modalPhone) elements.modalPhone.innerText = c.phone || "";
    
    const durationEl = document.getElementById("modalCustomerDuration");
    if (durationEl) durationEl.innerText = c.duration || "02:15 min";

    const ratingEl = document.getElementById("modalCustomerRating");
    if (ratingEl) ratingEl.innerText = c.rating ? `${c.rating} / 5` : "5 / 5";

    const sent = c.sentiment || "Neutral";
    if (elements.modalSentiment) {
        const sentLower = sent.toLowerCase();
        const sentIcon = sentLower.includes("pos") ? "❇️ Positive" : sentLower.includes("neg") ? "😡 Negative" : "😐 Neutral";
        elements.modalSentiment.innerText = sentIcon;
        elements.modalSentiment.className = `sentiment-badge-clean ${sentLower}`;
    }

    const transcript = c.transcript || [];
    if (!transcript.length) {
        const placeholder = isLive 
            ? `<div class="text-muted live-connecting-box"><span class="spinner-dot"></span> Connecting live voice agent...</div>`
            : `<div class="text-muted" style="text-align: center; padding: 24px;">No spoken conversation recorded yet.<br>Click "Start Call" to initiate voice survey.</div>`;
        elements.modalConversation.innerHTML = placeholder;
        return;
    }

    const htmlContent = transcript.map(msg => {
        const isAI = msg.speaker === "ai";
        const label = isAI ? "🤖 Voice AI Agent" : `👤 ${c.name}`;
        return `
            <div class="chat-bubble ${isAI ? "ai" : "customer"} chat-bubble-animate">
                <span class="chat-speaker">${escapeHtml(label)}</span>
                <div>${escapeHtml(msg.text)}</div>
            </div>
        `;
    }).join("");

    if (elements.modalConversation.innerHTML !== htmlContent) {
        elements.modalConversation.innerHTML = htmlContent;
        elements.modalConversation.scrollTop = elements.modalConversation.scrollHeight;
    }
}

function setTableMessage(message) {
    if (elements.table) {
        elements.table.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 24px; color: var(--text-muted);">${escapeHtml(message)}</td>
            </tr>
        `;
    }
}

function setButtonLoading(button, loading, label) {
    if (!button) return;
    button.disabled = loading;
    button.innerText = label;
}

function showToast(message, isError = false) {
    if (!elements.toast) return;
    window.clearTimeout(state.toastTimer);
    elements.toast.innerText = message;
    elements.toast.className = `toast-notification active${isError ? " error" : ""}`;
    state.toastTimer = window.setTimeout(() => {
        elements.toast.className = "toast-notification";
    }, 3500);
}

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// =========================
// SETTINGS MANAGERS & SYNC
// =========================

async function loadSettings() {
    try {
        const res = await requestJson("/api/settings");
        if (res && res.success && res.settings) {
            state.settings = res.settings;
            populateSettingsUI(res.settings);
        }
    } catch (err) {
        console.warn("Failed to load settings:", err.message);
    }
}

function populateSettingsUI(s) {
    if (!s) return;
    
    // Settings Voice Select
    const settingsVoiceSelect = document.getElementById("settingsVoiceSelect");
    if (settingsVoiceSelect && state.voices.length) {
        settingsVoiceSelect.innerHTML = state.voices.map(v => {
            const isSelected = (v.id === (s.active_voice || state.activeVoiceId)) ? "selected" : "";
            const lang = v.accent || v.language || "Indic";
            return `<option value="${escapeHtml(v.id)}" ${isSelected}>${escapeHtml(v.name)} (${escapeHtml(lang)})</option>`;
        }).join("");
    }

    const speechRateInput = document.getElementById("settingsSpeechRate");
    const speechRateValue = document.getElementById("speechRateValue");
    if (speechRateInput) {
        speechRateInput.value = s.speaking_rate || 1.0;
        if (speechRateValue) speechRateValue.innerText = `${parseFloat(s.speaking_rate || 1.0).toFixed(2)}x`;
    }

    const langSelect = document.getElementById("settingsLanguage");
    if (langSelect && s.language) langSelect.value = s.language;

    const greetingInput = document.getElementById("settingsGreetingTemplate");
    if (greetingInput && s.greeting_template) greetingInput.value = s.greeting_template;

    const twilioPhoneInput = document.getElementById("settingsTwilioPhone");
    if (twilioPhoneInput && s.twilio_phone) twilioPhoneInput.value = s.twilio_phone;

    const durationSelect = document.getElementById("settingsMaxDuration");
    if (durationSelect && s.max_call_duration) durationSelect.value = s.max_call_duration;

    const autoRetryInput = document.getElementById("settingsAutoRetry");
    if (autoRetryInput) autoRetryInput.checked = Boolean(s.auto_retry);

    const callDelayInput = document.getElementById("settingsCallDelay");
    if (callDelayInput && s.call_delay_seconds) callDelayInput.value = s.call_delay_seconds;

    const instantAlertsInput = document.getElementById("settingsInstantAlerts");
    if (instantAlertsInput) instantAlertsInput.checked = Boolean(s.instant_alerts);

    const alertPhoneInput = document.getElementById("settingsAlertPhone");
    if (alertPhoneInput && s.alert_phone) alertPhoneInput.value = s.alert_phone;

    const alertEmailInput = document.getElementById("settingsAlertEmail");
    if (alertEmailInput && s.alert_email) alertEmailInput.value = s.alert_email;

    const adminUsernameInput = document.getElementById("settingsAdminUsername");
    if (adminUsernameInput && s.admin_username) adminUsernameInput.value = s.admin_username;

    const pollIntervalSelect = document.getElementById("settingsPollInterval");
    if (pollIntervalSelect && s.poll_interval_ms) pollIntervalSelect.value = s.poll_interval_ms;
}

async function saveSettings(e) {
    if (e) e.preventDefault();

    const newVoice = document.getElementById("settingsVoiceSelect")?.value;
    const speechRate = parseFloat(document.getElementById("settingsSpeechRate")?.value || "1.0");
    const lang = document.getElementById("settingsLanguage")?.value;
    const greeting = document.getElementById("settingsGreetingTemplate")?.value?.trim();
    const twilioPhone = document.getElementById("settingsTwilioPhone")?.value?.trim();
    const maxDuration = parseInt(document.getElementById("settingsMaxDuration")?.value || "3");
    const autoRetry = document.getElementById("settingsAutoRetry")?.checked;
    const callDelay = parseInt(document.getElementById("settingsCallDelay")?.value || "10");
    const instantAlerts = document.getElementById("settingsInstantAlerts")?.checked;
    const alertPhone = document.getElementById("settingsAlertPhone")?.value?.trim();
    const alertEmail = document.getElementById("settingsAlertEmail")?.value?.trim();
    const adminUser = document.getElementById("settingsAdminUsername")?.value?.trim();
    const adminPass = document.getElementById("settingsAdminPassword")?.value?.trim();
    const pollInterval = parseInt(document.getElementById("settingsPollInterval")?.value || "2500");

    const payload = {
        active_voice: newVoice,
        speaking_rate: speechRate,
        language: lang,
        greeting_template: greeting,
        twilio_phone: twilioPhone,
        max_call_duration: maxDuration,
        auto_retry: autoRetry,
        call_delay_seconds: callDelay,
        instant_alerts: instantAlerts,
        alert_phone: alertPhone,
        alert_email: alertEmail,
        admin_username: adminUser,
        poll_interval_ms: pollInterval
    };

    if (adminPass && adminPass.length > 0) {
        payload.admin_password = adminPass;
    }

    try {
        const saveBtn = document.getElementById("saveSettingsBtn");
        if (saveBtn) saveBtn.innerText = "⏳ Saving...";

        const res = await requestJson("/api/settings", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        if (res && res.success) {
            state.settings = res.settings;
            if (newVoice) {
                state.activeVoiceId = newVoice;
                renderVoiceSelector();
            }

            // Reset poll interval dynamically if updated
            if (state.pollInterval && pollInterval) {
                clearInterval(state.pollInterval);
                state.pollInterval = setInterval(() => {
                    loadCustomers(true);
                }, pollInterval);
            }

            showToast("✅ Settings saved and updated successfully!");
            const passInput = document.getElementById("settingsAdminPassword");
            if (passInput) passInput.value = "";
        }
    } catch (err) {
        showToast(`Failed to save settings: ${err.message}`, true);
    } finally {
        const saveBtn = document.getElementById("saveSettingsBtn");
        if (saveBtn) saveBtn.innerText = "💾 Save All Settings";
    }
}

async function resetDefaultSettings() {
    if (!confirm("Are you sure you want to reset all settings to default values?")) return;

    const defaultPayload = {
        active_voice: "Google.hi-IN-Wavenet-B",
        speaking_rate: 1.0,
        language: "hi-IN",
        greeting_template: "Hello {customer_name}! Thank you for choosing BCT Fibernet. We are calling to collect your valuable service feedback.",
        twilio_phone: "+919057262630",
        max_call_duration: 3,
        auto_retry: true,
        call_delay_seconds: 10,
        instant_alerts: true,
        alert_phone: "+919057262630",
        alert_email: "vikas@example.com",
        admin_username: "VIKAS",
        poll_interval_ms: 2500
    };

    try {
        const res = await requestJson("/api/settings", {
            method: "POST",
            body: JSON.stringify(defaultPayload)
        });

        if (res && res.success) {
            state.settings = res.settings;
            state.activeVoiceId = res.settings.active_voice;
            populateSettingsUI(res.settings);
            renderVoiceSelector();
            showToast("🔄 Reset settings to defaults!");
        }
    } catch (err) {
        showToast(`Failed to reset settings: ${err.message}`, true);
    }
}
