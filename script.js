let transactions = [];
let charts = {};

document.addEventListener("DOMContentLoaded", function () {
  const today = new Date();
  const currentMonth = today.toISOString().slice(0, 7);
  document.getElementById("monthSelector").value = currentMonth;
  document.getElementById("date").valueAsDate = today;

  loadTransactions();

  document
    .getElementById("monthSelector")
    .addEventListener("change", updateStatistics);
  document.getElementById("type").addEventListener("change", toggleCategory);
  document
    .getElementById("transactionForm")
    .addEventListener("submit", addTransaction);
  const dlBtn = document.getElementById("downloadCsvBtn");
  if (dlBtn) dlBtn.addEventListener("click", downloadCsv);
});

function toggleCategory() {
  const type = document.getElementById("type").value;
  const categoryGroup = document.getElementById("categoryGroup");
  categoryGroup.style.display = type === "expense" ? "block" : "none";
}

async function loadTransactions() {
  try {
    const response = await fetch("/api/transactions");
    transactions = await response.json();
    updateStatistics();
  } catch (error) {
    console.error("Error loading transactions:", error);
  }
}

async function addTransaction(e) {
  e.preventDefault();
  const type = document.getElementById("type").value;
  const data = {
    description: document.getElementById("description").value,
    amount: parseFloat(document.getElementById("amount").value),
    type: type,
    category:
      type === "expense" ? document.getElementById("category").value : "Income",
    date: document.getElementById("date").value,
  };

  try {
    const resp = await fetch("/api/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!resp.ok) {
      const errText = await resp
        .json()
        .catch(() => ({ error: "Server error" }));
      console.error("Failed to add transaction:", errText);
      alert(
        "Failed to add transaction: " +
          (errText.error || errText.message || JSON.stringify(errText))
      );
      return;
    }

    // success
    document.getElementById("transactionForm").reset();
    document.getElementById("date").valueAsDate = new Date();
    loadTransactions();
  } catch (error) {
    console.error("Error adding transaction:", error);
    alert("Failed to add transaction");
  }
}

async function deleteTransaction(id) {
  if (confirm("Are you sure you want to delete this transaction?")) {
    try {
      await fetch(`/api/transactions/${id}`, { method: "DELETE" });
      loadTransactions();
    } catch (error) {
      console.error("Error deleting transaction:", error);
      alert("Failed to delete transaction");
    }
  }
}

async function updateStatistics() {
  const month = document.getElementById("monthSelector").value;
  try {
    const response = await fetch(`/api/statistics/${month}`);
    const stats = await response.json();

    document.getElementById(
      "totalIncome"
    ).textContent = `₹${stats.totals.income.toFixed(2)}`;
    document.getElementById(
      "totalExpense"
    ).textContent = `₹${stats.totals.expense.toFixed(2)}`;
    const balance = stats.totals.income - stats.totals.expense;
    document.getElementById("balance").textContent = `₹${balance.toFixed(2)}`;

    updateCharts(stats);
    updateTransactionsList(month);
  } catch (error) {
    console.error("Error updating statistics:", error);
  }
}

function updateCharts(stats) {
  Object.values(charts).forEach((chart) => {
    if (chart) chart.destroy();
  });
  charts = {};

  if (stats.categories.length > 0) {
    const ctx = document.getElementById("categoryChart");
    charts.category = new Chart(ctx, {
      type: "pie",
      data: {
        labels: stats.categories.map((c) => c.name),
        datasets: [
          {
            data: stats.categories.map((c) => c.value),
            backgroundColor: [
              "#FF6384",
              "#36A2EB",
              "#FFCE56",
              "#4BC0C0",
              "#9966FF",
              "#FF9F40",
              "#4CAF50",
            ],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
      },
    });
  }

  if (stats.daily.length > 0) {
    const ctx = document.getElementById("dailyChart");
    charts.daily = new Chart(ctx, {
      type: "line",
      data: {
        labels: stats.daily.map((d) => d.date),
        datasets: [
          {
            label: "Daily Expense (₹)",
            data: stats.daily.map((d) => d.amount),
            borderColor: "#ef4444",
            backgroundColor: "rgba(239, 68, 68, 0.1)",
            tension: 0.1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
      },
    });
  }

  if (stats.monthly.length > 0) {
    const incomeData = stats.monthly.map((m) => ({ x: m.month, y: m.income }));
    const ctx = document.getElementById("incomeChart");
    charts.income = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Income (₹)",
            data: incomeData,
            borderColor: "#10b981",
            backgroundColor: "rgba(16, 185, 129, 0.1)",
            tension: 0.1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        scales: {
          x: { type: "category" },
        },
      },
    });

    const expenseData = stats.monthly.map((m) => ({
      x: m.month,
      y: m.expense,
    }));
    const ctx2 = document.getElementById("expenseChart");
    charts.expense = new Chart(ctx2, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Expense (₹)",
            data: expenseData,
            borderColor: "#ef4444",
            backgroundColor: "rgba(239, 68, 68, 0.1)",
            tension: 0.1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        scales: {
          x: { type: "category" },
        },
      },
    });
  }
}

function updateTransactionsList(month) {
  const filtered = transactions.filter((t) => t.date.startsWith(month));
  const listContainer = document.getElementById("transactionsList");

  if (filtered.length === 0) {
    listContainer.innerHTML =
      '<p style="text-align:center;color:#666;padding:20px;">No transactions for this month</p>';
    return;
  }

  const html = filtered
    .map(
      (t) => `
        <div class="transaction-item">
            <div class="transaction-info">
                <h4>${t.description}</h4>
                <p>${t.category} • ${t.date}</p>
            </div>
            <div>
                <span class="transaction-amount ${t.type}">
                    ${t.type === "income" ? "+" : "-"}₹${t.amount.toFixed(2)}
                </span>
                <button class="delete-btn" onclick="deleteTransaction(${
                  t.id
                })">Delete</button>
            </div>
        </div>
    `
    )
    .join("");

  listContainer.innerHTML = html;
}

function downloadCsv() {
  // Use selected month (YYYY-MM) if any, otherwise download all
  const month = document.getElementById("monthSelector").value;
  const url = month
    ? `/download/csv?month=${encodeURIComponent(month)}`
    : "/download/csv";
  // Use simple navigation to trigger browser download
  window.location.href = url;
}
