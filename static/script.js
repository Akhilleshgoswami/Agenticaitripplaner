let currentThreadId = localStorage.getItem("travel_thread_id") || null;
let latestAnswerMarkdown = "";

function setPrompt(text) {
  document.getElementById("userInput").value = text;
}

function setLoading(isLoading) {
  const sendBtn = document.getElementById("sendBtn");
  const btnText = document.getElementById("btnText");
  const btnLoader = document.getElementById("btnLoader");

  if (sendBtn) sendBtn.disabled = isLoading;

  if (isLoading) {
    if (btnText) btnText.classList.add("hidden");
    if (btnLoader) btnLoader.classList.remove("hidden");
  } else {
    if (btnText) btnText.classList.remove("hidden");
    if (btnLoader) btnLoader.classList.add("hidden");
  }
}

function setApprovalLoading(isLoading) {
  const approveBtn = document.getElementById("approveBtn");
  const reviseBtn = document.getElementById("reviseBtn");

  if (approveBtn) approveBtn.disabled = isLoading;
  if (reviseBtn) reviseBtn.disabled = isLoading;
}

function showError(message) {
  const errorBox = document.getElementById("errorBox");
  if (errorBox) {
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
  }
}

function hideError() {
  const errorBox = document.getElementById("errorBox");
  if (errorBox) {
    errorBox.classList.add("hidden");
    errorBox.textContent = "";
  }
}

function renderWorkflow(data) {
  const workflowSection = document.getElementById("workflowSection");
  const supervisorReasoning = document.getElementById("supervisorReasoning");
  const guardrailBadge = document.getElementById("guardrailBadge");
  const agentChips = document.getElementById("agentChips");

  if (!workflowSection) return;

  if (data.guardrail_allowed === false) {
    if (guardrailBadge) {
      guardrailBadge.textContent = "Guardrail Blocked";
      guardrailBadge.className = "guardrail-badge blocked";
    }
    if (supervisorReasoning) {
      supervisorReasoning.textContent = data.guardrail_reason || data.answer;
    }
    if (agentChips) agentChips.innerHTML = "";
    workflowSection.classList.remove("hidden");
    return;
  }

  if (guardrailBadge) {
    guardrailBadge.textContent = "Guardrail Passed";
    guardrailBadge.className = "guardrail-badge passed";
  }

  if (supervisorReasoning) {
    supervisorReasoning.textContent =
      data.supervisor_reasoning || "All specialist agents coordinated.";
  }

  if (agentChips) {
    agentChips.innerHTML = "";
    const agentLabels = {
      flight_agent: "✈️ Flight Agent",
      hotel_agent: "🏨 Hotel Agent",
      weather_agent: "🌤️ Weather MCP",
      budget_agent: "💰 Budget Analyst",
      itinerary_agent: "🗺️ Itinerary Planner",
    };

    const agents = data.selected_agents || [
      "flight_agent",
      "hotel_agent",
      "weather_agent",
      "budget_agent",
      "itinerary_agent",
    ];

    agents.forEach((agent) => {
      const chip = document.createElement("span");
      chip.className = "agent-chip";
      chip.textContent = agentLabels[agent] || agent;
      agentChips.appendChild(chip);
    });
  }

  workflowSection.classList.remove("hidden");
}

function showResult(data) {
  latestAnswerMarkdown = data.answer || "";

  const resultSection = document.getElementById("resultSection");
  const resultBox = document.getElementById("resultBox");
  const resultTitle = document.getElementById("resultTitle");
  const threadInfo = document.getElementById("threadInfo");
  const approvalSection = document.getElementById("approvalSection");
  const approvalRequest = document.getElementById("approvalRequest");

  if (threadInfo) {
    threadInfo.textContent = `Thread ID: ${data.thread_id}`;
  }

  if (resultTitle) {
    resultTitle.textContent = data.requires_approval
      ? "Draft Itinerary (Pending Review)"
      : "Your AI Travel Plan";
  }

  if (resultBox) {
    if (typeof marked !== "undefined") {
      resultBox.innerHTML = marked.parse(latestAnswerMarkdown);
    } else {
      resultBox.innerText = latestAnswerMarkdown;
    }
  }

  if (resultSection) {
    resultSection.classList.remove("hidden");
  }

  // Handle Human-in-the-Loop review section
  if (data.requires_approval && approvalSection) {
    if (approvalRequest && data.approval_request) {
      approvalRequest.textContent = data.approval_request;
    }
    approvalSection.classList.remove("hidden");
    approvalSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } else if (approvalSection) {
    approvalSection.classList.add("hidden");
    if (resultSection) {
      resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
}

async function sendMessage() {
  hideError();

  const input = document.getElementById("userInput");
  const message = input.value.trim();

  if (!message) {
    showError("Please enter your travel request first.");
    return;
  }

  setLoading(true);

  try {
    const response = await fetch("/api/travel", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: message,
        thread_id: currentThreadId,
      }),
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Something went wrong.");
    }

    currentThreadId = data.thread_id;
    localStorage.setItem("travel_thread_id", currentThreadId);

    renderWorkflow(data);
    showResult(data);
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false);
  }
}

async function submitApproval(approved) {
  hideError();

  if (!currentThreadId) {
    showError("No active travel planning thread found.");
    return;
  }

  const feedbackInput = document.getElementById("approvalFeedback");
  const feedback = feedbackInput ? feedbackInput.value.trim() : "";

  setApprovalLoading(true);

  try {
    const response = await fetch("/api/travel/approval", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        thread_id: currentThreadId,
        approved: approved,
        feedback: feedback,
      }),
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Failed to submit approval.");
    }

    showResult(data);
  } catch (error) {
    showError(error.message);
  } finally {
    setApprovalLoading(false);
  }
}

function copyResult() {
  const resultBox = document.getElementById("resultBox");
  const text = resultBox ? resultBox.innerText : "";

  if (!text) return;

  navigator.clipboard
    .writeText(text)
    .then(() => {
      const copyBtn = document.querySelector(".copy-btn");
      if (copyBtn) {
        const oldText = copyBtn.textContent;
        copyBtn.textContent = "Copied!";
        setTimeout(() => {
          copyBtn.textContent = oldText;
        }, 1400);
      }
    })
    .catch(() => {
      showError("Could not copy result.");
    });
}

function downloadPDF() {
  const pdfContent = document.getElementById("pdfContent");

  if (!latestAnswerMarkdown || !pdfContent) {
    showError("No travel plan available to download.");
    return;
  }

  const downloadBtn = document.querySelector(".download-btn");
  const oldText = downloadBtn ? downloadBtn.textContent : "";

  if (downloadBtn) {
    downloadBtn.textContent = "Preparing PDF...";
    downloadBtn.disabled = true;
  }

  const options = {
    margin: 0.5,
    filename: "ai-travel-plan.pdf",
    image: {
      type: "jpeg",
      quality: 0.98,
    },
    html2canvas: {
      scale: 2,
      useCORS: true,
      backgroundColor: "#ffffff",
    },
    jsPDF: {
      unit: "in",
      format: "a4",
      orientation: "portrait",
    },
    pagebreak: {
      mode: ["avoid-all", "css", "legacy"],
    },
  };

  html2pdf()
    .set(options)
    .from(pdfContent)
    .save()
    .then(() => {
      if (downloadBtn) {
        downloadBtn.textContent = oldText;
        downloadBtn.disabled = false;
      }
    })
    .catch(() => {
      if (downloadBtn) {
        downloadBtn.textContent = oldText;
        downloadBtn.disabled = false;
      }
      showError("Could not download PDF.");
    });
}

document.addEventListener("keydown", function (event) {
  if (event.ctrlKey && event.key === "Enter") {
    sendMessage();
  }
});
