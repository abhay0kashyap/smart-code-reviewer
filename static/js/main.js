const codeEditor = document.getElementById("codeEditor");
const runBtn = document.getElementById("runBtn");
const aiFixBtn = document.getElementById("aiFixBtn");
const aiAssistBtn = document.getElementById("aiAssistBtn");
const applyFixBtn = document.getElementById("applyFixBtn");
const clearBtn = document.getElementById("clearBtn");

const loader = document.getElementById("loader");
const statusBadge = document.getElementById("statusBadge");

const outputPanel = document.getElementById("outputPanel");
const errorType = document.getElementById("errorType");
const errorMessage = document.getElementById("errorMessage");
const errorLine = document.getElementById("errorLine");
const tracebackPanel = document.getElementById("tracebackPanel");
const highlightPanel = document.getElementById("highlightPanel");
const explanationPanel = document.getElementById("explanationPanel");
const aiPrompt = document.getElementById("aiPrompt");
const aiAdvicePanel = document.getElementById("aiAdvicePanel");
const fixedCodePreview = document.getElementById("fixedCodePreview");

let latestFixedCode = "";
let latestErrorText = "";
let latestErrorType = "";
let latestErrorMessage = "";
let latestErrorLine = null;
let latestRunCode = "";

function setText(el, value) {
    if (el) el.textContent = String(value);
}

function setValue(el, value) {
    if (el) el.value = String(value);
}

if (codeEditor && !codeEditor.value.trim()) {
    codeEditor.value = [
        "# Write Python code",
        "name = 'Abhay'",
        "print('Hello', name/)",
    ].join("\n");
}

if (runBtn) runBtn.addEventListener("click", runCode);
if (aiFixBtn) aiFixBtn.addEventListener("click", aiFixCode);
if (aiAssistBtn) aiAssistBtn.addEventListener("click", aiAssistCode);
if (applyFixBtn) applyFixBtn.addEventListener("click", applyFixedCode);
if (clearBtn) clearBtn.addEventListener("click", clearAll);

window.addEventListener("error", () => setLoading(false, "UI error"));
window.addEventListener("unhandledrejection", () => setLoading(false, "Request failed"));

async function postJson(url, body, timeoutMs = 20000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    let response;
    try {
        response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            signal: controller.signal,
        });
    } catch (error) {
        clearTimeout(timer);
        throw new Error(error?.name === "AbortError" ? "Request timed out." : "Network request failed.");
    }

    let payload;
    try {
        payload = await response.json();
    } catch {
        clearTimeout(timer);
        throw new Error("Server returned invalid JSON.");
    }

    clearTimeout(timer);

    if (!response.ok) {
        throw new Error(payload.error || payload.message || `Request failed (${response.status})`);
    }

    return payload;
}

function setLoading(loading, statusText = "Ready") {
    if (loader) loader.classList.toggle("hidden", !loading);
    if (runBtn) runBtn.disabled = loading;
    if (aiFixBtn) aiFixBtn.disabled = loading;
    if (aiAssistBtn) aiAssistBtn.disabled = loading;
    if (clearBtn) clearBtn.disabled = loading;
    if (applyFixBtn && loading) applyFixBtn.disabled = true;
    if (statusBadge) statusBadge.textContent = loading ? "Processing..." : statusText;
}

function renderRunResult(payload, sourceCode) {
    const execution = payload.execution || {};
    const explanation = payload.explanation || null;

    if (execution.success) {
        latestErrorText = "";
        latestErrorType = "";
        latestErrorMessage = "";
        latestErrorLine = null;
        setText(outputPanel, execution.stdout || execution.output || "Program executed with no output.");
        setText(errorType, "None");
        setText(errorMessage, "None");
        setText(errorLine, "None");
        setText(tracebackPanel, "No traceback.");
        setText(highlightPanel, "No highlighted line.");
        setText(explanationPanel, "Code executed successfully.");
        return;
    }

    setText(outputPanel, execution.stdout || "No program output.");
    setText(errorType, execution.error_type || "ExecutionError");
    setText(errorMessage, execution.error_message || "Unknown error");
    setText(errorLine, execution.error_line ?? "Unknown");
    setText(tracebackPanel, execution.traceback || execution.stderr || "No traceback.");

    latestErrorText = execution.traceback || execution.error || execution.error_message || "";
    latestErrorType = String(execution.error_type || "");
    latestErrorMessage = String(execution.error_message || "");
    latestErrorLine = Number.isInteger(execution.error_line) ? execution.error_line : null;
    const base = explanation?.explanation || "No explanation available.";
    const concept = explanation?.concept ? ` Concept: ${explanation.concept}` : "";
    setText(explanationPanel, `${base}${concept}`);

    renderHighlightedLine(sourceCode, execution.error_line);
}

function renderHighlightedLine(code, lineNumber) {
    if (!highlightPanel) return;

    const lines = String(code || "").split("\n");
    if (!lineNumber || lineNumber < 1 || lineNumber > lines.length) {
        setText(highlightPanel, "No highlighted line.");
        return;
    }

    const html = lines
        .map((line, idx) => {
            const n = idx + 1;
            const escaped = escapeHtml(line);
            if (n === lineNumber) {
                return `<span class="highlight-line">${n}: ${escaped}</span>`;
            }
            return `${n}: ${escaped}`;
        })
        .join("\n");

    highlightPanel.innerHTML = html;
}

function renderFixedPreview(autofix) {
    if (!fixedCodePreview || !applyFixBtn) return;

    const fix = autofix || {};
    if (typeof fix.fix_available !== "boolean" || typeof fix.fixed_code !== "string") {
        latestFixedCode = "";
        fixedCodePreview.value = "Invalid fix response from backend.";
        applyFixBtn.disabled = true;
        return;
    }

    if (fix.fix_available && fix.fixed_code && fix.fixed_code.trim()) {
        latestFixedCode = fix.fixed_code;
        fixedCodePreview.value = fix.fixed_code;
        applyFixBtn.disabled = false;
        return;
    }

    latestFixedCode = "";
    fixedCodePreview.value = "No fixed code preview yet.";
    applyFixBtn.disabled = true;
}

function renderTutorResult(payload) {
    if (!aiAdvicePanel) return;

    const assistant = payload?.assistant || {};
    const message = String(assistant.assistant_message || "No tutor guidance available.");
    const suggestions = Array.isArray(assistant.suggestions) ? assistant.suggestions : [];
    const adviceText = suggestions.length
        ? `${message}\n\nSuggestions:\n- ${suggestions.join("\n- ")}`
        : message;

    aiAdvicePanel.textContent = adviceText;

    if (!fixedCodePreview || !applyFixBtn || !codeEditor) return;

    const generatedCode = String(assistant.generated_code || "");
    if (assistant.can_apply && generatedCode.trim() && generatedCode.trim() !== codeEditor.value.trim()) {
        latestFixedCode = generatedCode;
        fixedCodePreview.value = generatedCode;
        applyFixBtn.disabled = false;
    }
}

async function runCode() {
    if (!codeEditor) return;

    const code = codeEditor.value;
    let status = "Ready";
    setLoading(true, "Running...");

    try {
        const runPayload = await postJson("/run", { code }, 12000);
        latestRunCode = code;
        renderRunResult(runPayload, code);
        status = runPayload.execution?.success ? "Run successful" : "Run failed";
    } catch (err) {
        setText(outputPanel, "");
        setText(tracebackPanel, String(err.message || err));
        status = "Run request failed";
    } finally {
        setLoading(false, status);
    }
}

async function aiFixCode() {
    if (!codeEditor) return;

    const code = codeEditor.value;
    if (!latestErrorType || latestErrorType === "None" || latestRunCode !== code) {
        alert("Run code first to detect error");
        return;
    }

    let status = "Ready";
    const originalText = aiFixBtn ? aiFixBtn.textContent : "AI Auto Fix";
    if (aiFixBtn) {
        aiFixBtn.textContent = "Fixing with AI...";
        aiFixBtn.disabled = true;
    }
    setLoading(true, "Fixing with AI...");

    try {
        const fixPayload = await postJson(
            "/ai-fix",
            {
                original_code: code,
                error_type: latestErrorType,
                error_message: latestErrorMessage,
                error_line: latestErrorLine,
                traceback: latestErrorText,
            },
            30000
        );

        const fixedCode = String(fixPayload.fixed_code || "").trim();
        if (fixedCode) {
            setValue(fixedCodePreview, fixedCode);
            latestFixedCode = fixedCode;
            if (applyFixBtn) applyFixBtn.disabled = false;
            status = "Fixed code generated";
            if (fixPayload.explanation) {
                setText(explanationPanel, String(fixPayload.explanation));
            }
            if (fixPayload.improvements) {
                setText(aiAdvicePanel, String(fixPayload.improvements));
            }
        } else {
            setValue(fixedCodePreview, fixPayload.message || "No fixed code generated.");
            if (applyFixBtn) applyFixBtn.disabled = true;
            status = fixPayload.message || "No auto fix available";
        }
    } catch (err) {
        setValue(fixedCodePreview, `Auto-fix failed: ${String(err.message || err)}`);
        if (applyFixBtn) applyFixBtn.disabled = true;
        status = "Auto-fix request failed";
    } finally {
        setLoading(false, status);
        if (aiFixBtn) {
            aiFixBtn.disabled = false;
            aiFixBtn.textContent = originalText || "AI Auto Fix";
        }
    }
}

async function aiAssistCode() {
    if (!codeEditor || !aiPrompt) return;

    const code = codeEditor.value;
    const prompt = aiPrompt.value;

    if (!code.trim() && !prompt.trim()) {
        setText(aiAdvicePanel, "Write code or enter a question for AI Tutor.");
        return;
    }

    let status = "Ready";
    setLoading(true, "Asking AI Tutor...");

    try {
        const assistPayload = await postJson("/ai_assist", { code, prompt, error: latestErrorText }, 35000);
        if (assistPayload.execution) {
            renderRunResult(
                {
                    execution: assistPayload.execution,
                    explanation: assistPayload.explanation || {},
                },
                code
            );
        }
        renderTutorResult(assistPayload);
        status = "AI tutor response ready";
    } catch (err) {
        setText(aiAdvicePanel, `AI Tutor failed: ${String(err.message || err)}`);
        status = "AI tutor request failed";
    } finally {
        setLoading(false, status);
    }
}

function applyFixedCode() {
    if (!codeEditor || !fixedCodePreview || !applyFixBtn) return;

    codeEditor.value = fixedCodePreview.value;
    latestFixedCode = codeEditor.value;
    applyFixBtn.disabled = true;
    setText(statusBadge, "Fixed code applied. Run again.");
}

function clearAll() {
    if (codeEditor) codeEditor.value = "";
    setText(outputPanel, "Run code to see output.");
    setText(errorType, "None");
    setText(errorMessage, "None");
    setText(errorLine, "None");
    setText(tracebackPanel, "No traceback.");
    setText(highlightPanel, "No highlighted line.");
    setText(explanationPanel, "No explanation yet.");
    setValue(aiPrompt, "");
    setText(aiAdvicePanel, "No tutor suggestions yet.");
    setValue(fixedCodePreview, "No fixed code preview yet.");

    latestFixedCode = "";
    if (applyFixBtn) applyFixBtn.disabled = true;
    setText(statusBadge, "Cleared");
    if (loader) loader.classList.add("hidden");
}

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
