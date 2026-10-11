"use strict";
const $ = id => document.getElementById(id);
let polling = null;
let selectedRun = null;
const statusNames = {queued:"Đang chờ",running:"Đang xử lý",completed:"Hoàn thành",incomplete:"Chưa đủ dữ liệu",failed:"Thất bại"};
async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Yêu cầu không hợp lệ (${response.status})`);
  return data;
}
function showError(message) { $("error").textContent = message; $("error").hidden = !message; }
function renderFailure(message) {
  $("downloads").hidden = true;
  $("report-title").textContent = "Chưa tạo được báo cáo";
  $("report-meta").textContent = "";
  $("articles").replaceChildren(node("div", "placeholder", message || "Agent thất bại. Xem thông báo lỗi và thử lại khi phù hợp."));
}
function handleRunError(error, id) {
  if (id && selectedRun !== id) return;
  clearInterval(polling); polling = null;
  $("run-button").disabled = false;
  $("status").textContent = "Không tải được kết quả";
  const message = error.message + ". Làm mới lịch sử để kiểm tra lượt chạy.";
  showError(message); renderFailure(message);
}
function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function renderSteps(steps) {
  $("steps").replaceChildren(...steps.map(step => {
    const li = node("li");
    li.append(node("strong", "", `${step.step}. ${step.agent} · ${step.action}`),
      node("small", "", typeof step.detail === "string" ? step.detail : JSON.stringify(step.detail)));
    return li;
  }));
}
function renderReport(report) {
  $("report-title").textContent = report.topic;
  $("report-meta").textContent = `${report.mode.toUpperCase()} · ${report.analysis.findings.length}/${report.requested_count} mục · ${report.api_calls} lượt model · ${new Date(report.created_at).toLocaleString("vi-VN")} ${report.warning}`;
  const articles = new Map(report.articles.map(a => [a.id, a]));
  const cards = report.analysis.findings.map(f => {
    const a = articles.get(f.article_id);
    const card = node("article", "card");
    card.append(node("div", "category", f.category), node("h3", "", a.title),
      node("p", "", f.summary), node("blockquote", "", f.evidence_quote), node("p", "limitation", f.limitation));
    const link = node("a", "source", `${a.source} ↗ ${a.url}`);
    const url = new URL(a.url);
    if (["https:", "http:"].includes(url.protocol)) link.href = url.href;
    link.target = "_blank"; link.rel = "noopener noreferrer";
    card.append(link);
    return card;
  });
  if (!cards.length) cards.push(node("div", "placeholder", "Không có bài đủ căn cứ; hãy thử chủ đề khác."));
  $("articles").replaceChildren(...cards);
  $("downloads").hidden = false;
  for (const format of ["md", "json"]) $("download-"+format).href = `/api/reports/${report.id}/download?format=${format}`;
}
async function loadHistory() {
  const history = await api("/api/runs");
  $("history").replaceChildren(...history.map(run => {
    const button = node("button", "", run.request);
    button.type = "button";
    button.append(node("small", "", `${run.mode.toUpperCase()} · ${statusNames[run.status]} · ${new Date(run.created_at).toLocaleString("vi-VN")}`));
    button.onclick = () => watchRun(run.id).catch(error => showError(error.message));
    return button;
  }));
  if (!history.length) $("history").append(node("p", "", "Chưa có lượt chạy."));
}
async function updateRun(id) {
  const run = await api(`/api/runs/${id}`);
  if (selectedRun !== id) return;
  $("status").textContent = statusNames[run.status] || run.status;
  renderSteps(run.steps);
  const active = ["queued", "running"].includes(run.status);
  $("run-button").disabled = active;
  if (!active) {
    clearInterval(polling); polling = null;
    showError(run.error || "");
    if (run.report_id) {
      const report = await api(`/api/reports/${run.report_id}`);
      if (selectedRun !== id) return;
      renderReport(report);
    } else {
      renderFailure(run.error || "Lượt chạy kết thúc nhưng không có báo cáo để hiển thị.");
    }
    await loadHistory();
  }
  return active;
}
async function watchRun(id) {
  clearInterval(polling);
  selectedRun = id;
  showError(""); $("downloads").hidden = true;
  $("report-title").textContent = "Bản tin của bạn";
  $("report-meta").textContent = "";
  $("articles").replaceChildren(node("div", "placeholder", "Đang tải kết quả…"));
  try {
    if (await updateRun(id)) {
      polling = setInterval(() => updateRun(id).catch(error => handleRunError(error, id)), 1000);
    }
  } catch (error) { handleRunError(error, id); }
}
$("run-form").addEventListener("submit", async event => {
  event.preventDefault(); showError(""); $("run-button").disabled = true;
  try {
    const run = await api("/api/runs", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({request:$("request").value.trim()})});
    await watchRun(run.id);
  } catch (error) { handleRunError(error); }
});
$("refresh").onclick = () => loadHistory().catch(error => showError(error.message));
async function init() {
  const config = await api("/api/config");
  $("mode").textContent = config.mode === "mock" ? "● MOCK / OFFLINE" : "● GEMINI / LIVE";
  $("mode-note").textContent = config.mode === "mock" ? "DEMO OFFLINE: Agent và bài báo đều được mô phỏng. Nguồn example.com là dữ liệu mẫu, không phải tin thật." : "LIVE: Gemini lựa chọn công cụ và phân tích RSS thật. Kết quả dựa trên trích đoạn; cần đối chiếu nguồn.";
  $("limits").textContent = `Tối đa ${config.max_api_calls} lượt model · ${config.max_steps} bước/Collector · ${config.max_plans} kế hoạch`;
  await loadHistory();
}
init().catch(error => showError(error.message));
