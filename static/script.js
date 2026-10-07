let currentThreadId = localStorage.getItem("travel_thread_id") || null;
let latestAnswerMarkdown = "";
let workTimer = null;

const AGENT_LABELS = {
    flight_agent: "Flights",
    hotel_agent: "Hotels",
    weather_agent: "Weather",
    budget_agent: "Budget",
    itinerary_agent: "Itinerary",
};

const CONSTRAINT_LABELS = [
    ["origin", "From"],
    ["destination", "To"],
    ["duration", "Length"],
    ["budget", "Budget"],
    ["travel_style", "Style"],
];

const PLAN_STEPS = [
    "Reading your request",
    "Checking flights and hotels",
    "Checking weather and budget",
    "Writing a draft for you to review",
];

const REVIEW_STEPS = [
    "Applying your review",
    "Writing the finished plan",
];

function setPrompt(text) {
    const input = document.getElementById("userInput");
    input.value = text;
    input.focus();
}

function setBusy(isBusy) {
    document.getElementById("sendBtn").disabled = isBusy;
    document.getElementById("approveBtn").disabled = isBusy;
    document.getElementById("reviseBtn").disabled = isBusy;
    document.getElementById("newTripBtn").disabled = isBusy;
    document.getElementById("userInput").disabled = isBusy;
    document.querySelectorAll(".chip").forEach((chip) => {
        chip.disabled = isBusy;
    });
}

function showWork(steps) {
    const status = document.getElementById("workStatus");
    const text = document.getElementById("workStatusText");
    let index = 0;

    const tick = () => {
        text.textContent = steps[index % steps.length];
        index += 1;
    };

    clearWork();
    tick();
    status.classList.remove("hidden");
    workTimer = window.setInterval(tick, 4000);
}

function clearWork() {
    if (workTimer) {
        window.clearInterval(workTimer);
        workTimer = null;
    }
    document.getElementById("workStatus").classList.add("hidden");
    document.getElementById("workStatusText").textContent = "";
}

function setLoading(isLoading, mode) {
    const btnText = document.getElementById("btnText");
    const btnLoader = document.getElementById("btnLoader");

    setBusy(isLoading);

    if (isLoading) {
        btnText.textContent = mode === "review" ? "Updating" : "Planning";
        btnLoader.classList.remove("hidden");
        showWork(mode === "review" ? REVIEW_STEPS : PLAN_STEPS);
        return;
    }

    btnText.textContent = "Plan this trip";
    btnLoader.classList.add("hidden");
    clearWork();
}

function showError(message) {
    const errorBox = document.getElementById("errorBox");
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

function hideError() {
    const errorBox = document.getElementById("errorBox");
    errorBox.classList.add("hidden");
    errorBox.textContent = "";
}

function refreshContinueNote() {
    const note = document.getElementById("continueNote");
    if (!currentThreadId) {
        note.textContent = "";
        note.classList.add("hidden");
        return;
    }

    note.textContent = "This browser will continue your last trip. Start a new trip for a fresh plan.";
    note.classList.remove("hidden");
}

function showEmpty() {
    document.getElementById("emptyState").classList.remove("hidden");
}

function hideEmpty() {
    document.getElementById("emptyState").classList.add("hidden");
}

function renderMarkdown(element, text) {
    const value = text ? String(text) : "";
    if (!value.trim()) {
        element.innerHTML = "";
        return;
    }

    if (typeof marked !== "undefined") {
        element.innerHTML = marked.parse(value);
        return;
    }

    element.innerText = value;
}

function displayText(value) {
    if (value == null) {
        return "";
    }
    if (typeof value === "string") {
        return value.trim();
    }
    if (Array.isArray(value)) {
        return value.map(displayText).filter(Boolean).join("\n\n").trim();
    }
    if (typeof value === "object") {
        if (typeof value.text === "string") {
            return displayText(value.text);
        }
        if (typeof value.content === "string") {
            return displayText(value.content);
        }
        try {
            return JSON.stringify(value, null, 2);
        } catch (error) {
            return "";
        }
    }
    return String(value).trim();
}

function setPanel(panelId, boxId, text, asMarkdown) {
    const panel = document.getElementById(panelId);
    const box = document.getElementById(boxId);
    const value = displayText(text);

    if (!value) {
        box.textContent = "";
        panel.classList.add("hidden");
        panel.open = false;
        return;
    }

    if (asMarkdown) {
        renderMarkdown(box, value);
    } else {
        box.textContent = value;
    }
    panel.classList.remove("hidden");
}

function renderConstraints(constraints) {
    const row = document.getElementById("constraintRow");
    const source = constraints && typeof constraints === "object" ? constraints : {};
    row.replaceChildren();

    CONSTRAINT_LABELS.forEach(([key, label]) => {
        const value = source[key];
        if (!value || !String(value).trim()) {
            return;
        }

        const item = document.createElement("li");
        const name = document.createElement("span");
        const text = document.createElement("strong");
        name.textContent = label;
        text.textContent = String(value);
        item.append(name, text);
        row.append(item);
    });

    row.classList.toggle("hidden", row.childElementCount === 0);
}

function renderAgents(names) {
    const planMeta = document.getElementById("planMeta");
    const labels = (names || [])
        .map((name) => AGENT_LABELS[name] || name)
        .filter(Boolean);

    planMeta.replaceChildren(...labels.map((label) => {
        const pill = document.createElement("span");
        pill.textContent = label;
        return pill;
    }));
}

function showResult(data) {
    const answer = data.answer || "";
    latestAnswerMarkdown = answer;

    const resultSection = document.getElementById("resultSection");
    const reviewPanel = document.getElementById("reviewPanel");
    const resultEyebrow = document.getElementById("resultEyebrow");
    const pdfTitle = document.querySelector(".pdf-title");
    const threadInfo = document.getElementById("threadInfo");

    renderMarkdown(document.getElementById("resultBox"), answer);
    renderConstraints(data.trip_constraints);
    renderAgents(data.selected_agents);
    setPanel("weatherPanel", "weatherBox", data.weather_results, false);
    setPanel("budgetPanel", "budgetBox", data.budget_results, true);
    setPanel("flightPanel", "flightBox", data.flight_results, true);
    setPanel("hotelPanel", "hotelBox", data.hotel_results, false);

    threadInfo.textContent = data.thread_id ? `Reference ${String(data.thread_id).slice(-8)}` : "";
    threadInfo.title = data.thread_id || "";

    if (data.requires_approval) {
        resultEyebrow.textContent = "Draft ready for review";
        pdfTitle.textContent = "Draft itinerary";
        document.getElementById("approvalRequest").textContent =
            data.approval_request || "Review this draft before the final plan is written.";
        reviewPanel.classList.remove("hidden");
    } else {
        resultEyebrow.textContent = "Finished itinerary";
        pdfTitle.textContent = "TripMate itinerary";
        reviewPanel.classList.add("hidden");
        document.getElementById("feedbackInput").value = "";
    }

    hideEmpty();
    resultSection.classList.remove("hidden");
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function applyPlan(data) {
    if (data.guardrail_allowed === false) {
        document.getElementById("resultSection").classList.add("hidden");
        showEmpty();
        showError(data.guardrail_reason || data.answer || "This request is outside travel planning.");
        return;
    }

    currentThreadId = data.thread_id;
    localStorage.setItem("travel_thread_id", currentThreadId);
    refreshContinueNote();
    hideError();
    showResult(data);
}

function isBusy() {
    return document.getElementById("sendBtn").disabled;
}

async function sendMessage() {
    if (isBusy()) {
        return;
    }

    hideError();

    const message = document.getElementById("userInput").value.trim();
    if (!message) {
        showError("Write the trip first. Origin, destination, length, and budget help the most.");
        return;
    }

    setLoading(true, "plan");

    try {
        const response = await fetch("/api/travel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                thread_id: currentThreadId
            })
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Something went wrong.");
        }

        applyPlan(data);
    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

async function submitReview(approved) {
    if (isBusy()) {
        return;
    }

    hideError();

    if (!currentThreadId) {
        showError("There is no draft to review yet.");
        return;
    }

    setLoading(true, "review");

    try {
        const response = await fetch("/api/travel/resume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                thread_id: currentThreadId,
                approved: approved,
                feedback: document.getElementById("feedbackInput").value.trim()
            })
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Something went wrong.");
        }

        applyPlan(data);
    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

function startNewTrip() {
    currentThreadId = null;
    localStorage.removeItem("travel_thread_id");
    document.getElementById("userInput").value = "";
    document.getElementById("feedbackInput").value = "";
    document.getElementById("resultSection").classList.add("hidden");
    document.querySelectorAll(".chip").forEach((chip) => chip.classList.remove("is-selected"));
    hideError();
    showEmpty();
    refreshContinueNote();
    document.getElementById("userInput").focus();
}

function copyResult() {
    const text = document.getElementById("pdfContent").innerText;
    if (!text) {
        return;
    }

    const copyBtn = document.getElementById("copyPlanBtn");
    navigator.clipboard.writeText(text)
        .then(() => {
            const oldText = copyBtn.textContent;
            copyBtn.textContent = "Copied";
            window.setTimeout(() => {
                copyBtn.textContent = oldText;
            }, 1400);
        })
        .catch(() => {
            showError("Could not copy the plan.");
        });
}

function downloadPDF() {
    const pdfContent = document.getElementById("pdfContent");
    if (!latestAnswerMarkdown || !pdfContent) {
        showError("There is no plan to download yet.");
        return;
    }

    const downloadBtn = document.getElementById("downloadPlanBtn");
    const oldText = downloadBtn.textContent;
    downloadBtn.textContent = "Preparing PDF";
    downloadBtn.disabled = true;

    html2pdf()
        .set({
            margin: 0.5,
            filename: "tripmate-itinerary.pdf",
            image: { type: "jpeg", quality: 0.98 },
            html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff" },
            jsPDF: { unit: "in", format: "a4", orientation: "portrait" },
            pagebreak: { mode: ["css", "legacy"] }
        })
        .from(pdfContent)
        .save()
        .then(() => {
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
        })
        .catch(() => {
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
            showError("Could not download the PDF.");
        });
}

document.getElementById("sendBtn").addEventListener("click", sendMessage);
document.getElementById("newTripBtn").addEventListener("click", startNewTrip);
document.getElementById("copyPlanBtn").addEventListener("click", copyResult);
document.getElementById("downloadPlanBtn").addEventListener("click", downloadPDF);
document.getElementById("reviseBtn").addEventListener("click", () => submitReview(false));
document.getElementById("approveBtn").addEventListener("click", () => submitReview(true));

document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        document.querySelectorAll(".chip").forEach((item) => item.classList.remove("is-selected"));
        chip.classList.add("is-selected");
        setPrompt(chip.dataset.prompt || "");
    });
});

document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }
});

refreshContinueNote();
