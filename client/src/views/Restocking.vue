<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.subtitle') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="successOrder" class="success-banner" role="status">
        <div>
          <strong>{{ t('restocking.success.title') }}</strong>
          <span>
            {{ t('restocking.success.message', { orderNumber: successOrder.order_number, days: successOrder.lead_time_days }) }}
          </span>
        </div>
        <router-link to="/orders#submitted-orders" class="banner-link">
          {{ t('restocking.success.viewOrders') }}
        </router-link>
      </div>

      <div class="card budget-card">
        <div class="budget-header">
          <label for="budget-slider" class="budget-label">{{ t('restocking.budget') }}</label>
          <span class="budget-value">{{ formatCurrency(budget, currentCurrency) }}</span>
        </div>
        <input
          id="budget-slider"
          v-model.number="budget"
          type="range"
          min="0"
          :max="maxBudget"
          step="500"
          class="budget-slider"
          :aria-label="t('restocking.budgetSlider')"
        />
        <div class="slider-scale">
          <span>{{ formatCurrency(0, currentCurrency) }}</span>
          <span>{{ formatCurrency(maxBudget, currentCurrency) }}</span>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ formatCurrency(budget, currentCurrency) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.spent') }}</div>
          <div class="stat-value">{{ formatCurrency(totalCost, currentCurrency) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ formatCurrency(remaining, currentCurrency) }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }} ({{ recommendations.length }})</h3>
          <button
            class="btn-primary"
            :disabled="recommendations.length === 0"
            @click="openConfirm"
          >
            {{ t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="recommendations.length === 0" class="empty-note">{{ t('restocking.empty') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="num">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in recommendations" :key="rec.item_sku">
                <td>
                  <div class="item-name">{{ translateProductName(rec.item_name) }}</div>
                  <div class="item-sku">{{ rec.item_sku }}</div>
                </td>
                <td><span :class="['badge', rec.trend]">{{ t(`trends.${rec.trend}`) }}</span></td>
                <td class="num">{{ rec.quantity.toLocaleString() }}</td>
                <td class="num">{{ formatCurrencyWithDecimals(rec.unit_cost, currentCurrency, 2) }}</td>
                <td class="num"><strong>{{ formatCurrency(rec.lineTotal, currentCurrency) }}</strong></td>
                <td class="num">{{ t('restocking.days', { count: rec.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showConfirm" class="modal-overlay" @click="closeConfirm">
          <div class="modal-container" role="dialog" aria-modal="true" @click.stop>
            <div class="modal-header">
              <h3 class="modal-title">{{ t('restocking.confirm.title') }}</h3>
              <button class="close-button" :disabled="submitting" @click="closeConfirm">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
              </button>
            </div>

            <div class="modal-body">
              <p class="modal-summary">{{ t('restocking.confirm.summary') }}</p>

              <div class="summary-grid">
                <div class="summary-card">
                  <div class="summary-label">{{ t('restocking.confirm.total') }}</div>
                  <div class="summary-value">{{ formatCurrency(totalCost, currentCurrency) }}</div>
                </div>
                <div class="summary-card">
                  <div class="summary-label">{{ t('restocking.confirm.leadTime') }}</div>
                  <div class="summary-value">{{ t('restocking.days', { count: overallLeadTime }) }}</div>
                </div>
              </div>

              <ul class="confirm-list">
                <li v-for="rec in recommendations" :key="rec.item_sku">
                  <span>{{ translateProductName(rec.item_name) }} x {{ rec.quantity.toLocaleString() }}</span>
                  <span>{{ formatCurrency(rec.lineTotal, currentCurrency) }}</span>
                </li>
              </ul>

              <div v-if="submitError" class="error submit-error">{{ submitError }}</div>
            </div>

            <div class="modal-footer">
              <button class="btn-secondary" :disabled="submitting" @click="closeConfirm">
                {{ t('common.cancel') }}
              </button>
              <button class="btn-primary" :disabled="submitting" @click="confirmOrder">
                {{ submitting ? t('restocking.confirm.submitting') : t('restocking.confirm.submit') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

const { t, currentCurrency, translateProductName } = useI18n()

const BUDGET_STEP = 500

const forecasts = ref([])
const loading = ref(true)
const error = ref(null)
const budget = ref(0)

const showConfirm = ref(false)
const submitting = ref(false)
const submitError = ref(null)
const successOrder = ref(null)

// Items whose forecast exceeds current demand, with the gap as the suggested quantity
const gapItems = computed(() => {
  return forecasts.value
    .map(f => ({ ...f, quantity: f.forecasted_demand - f.current_demand }))
    .filter(f => f.quantity > 0)
    .sort((a, b) => b.quantity - a.quantity)
})

// Slider max: cost of restocking every gap item, rounded up to the next step
const maxBudget = computed(() => {
  const total = gapItems.value.reduce((sum, i) => sum + i.quantity * i.unit_cost, 0)
  return Math.max(BUDGET_STEP, Math.ceil(total / BUDGET_STEP) * BUDGET_STEP)
})

// Greedy fill by largest gap first; an item that does not fit is skipped and the next is tried
const recommendations = computed(() => {
  const picked = []
  let spent = 0
  for (const item of gapItems.value) {
    const lineTotal = item.quantity * item.unit_cost
    if (spent + lineTotal <= budget.value) {
      picked.push({ ...item, lineTotal })
      spent += lineTotal
    }
  }
  return picked
})

const totalCost = computed(() => recommendations.value.reduce((sum, r) => sum + r.lineTotal, 0))
const remaining = computed(() => Math.max(0, budget.value - totalCost.value))
const overallLeadTime = computed(() => Math.max(0, ...recommendations.value.map(r => r.lead_time_days)))

const loadData = async () => {
  try {
    loading.value = true
    error.value = null
    forecasts.value = await api.getDemandForecasts()
    // Start at roughly half of the maximum so the slider shows a meaningful result
    budget.value = Math.round(maxBudget.value / 2 / BUDGET_STEP) * BUDGET_STEP
  } catch (err) {
    error.value = t('restocking.errors.load')
    console.error('Failed to load demand forecasts:', err)
  } finally {
    loading.value = false
  }
}

const openConfirm = () => {
  if (recommendations.value.length === 0) return
  submitError.value = null
  showConfirm.value = true
}

const closeConfirm = () => {
  if (submitting.value) return
  showConfirm.value = false
}

const confirmOrder = async () => {
  submitting.value = true
  submitError.value = null
  try {
    const order = await api.placeRestockingOrder({
      items: recommendations.value.map(r => ({ item_sku: r.item_sku, quantity: r.quantity })),
      budget: budget.value
    })
    successOrder.value = order
    showConfirm.value = false
  } catch (err) {
    // Prefer the backend's detail message (e.g. over budget); fall back to a generic one
    const detail = err.response?.data?.detail
    submitError.value = typeof detail === 'string' ? detail : t('restocking.errors.submit')
    console.error('Failed to place restocking order:', err)
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.success-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem 1.25rem;
  margin-bottom: 1.25rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  color: #166534;
  font-size: 0.875rem;
}

.success-banner strong {
  margin-right: 0.5rem;
}

.banner-link {
  color: #166534;
  font-weight: 600;
  text-decoration: underline;
  white-space: nowrap;
}

.budget-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
}

.budget-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  accent-color: #0f172a;
}

.slider-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.num {
  text-align: right;
}

.item-name {
  font-weight: 500;
  color: #0f172a;
}

.item-sku {
  font-size: 0.75rem;
  color: #64748b;
  font-family: 'Monaco', 'Courier New', monospace;
}

.empty-note {
  padding: 1.5rem;
  color: #64748b;
  font-size: 0.875rem;
  text-align: center;
}

.btn-primary,
.btn-secondary {
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s ease;
}

.btn-primary {
  background: #0f172a;
  color: white;
  border: 1px solid #0f172a;
}

.btn-primary:hover:not(:disabled) {
  background: #1e293b;
}

.btn-secondary {
  background: #f1f5f9;
  color: #334155;
  border: 1px solid #e2e8f0;
}

.btn-secondary:hover:not(:disabled) {
  background: #e2e8f0;
}

.btn-primary:disabled,
.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.submit-error {
  margin-top: 1rem;
}

/* Modal (same pattern as BacklogDetailModal) */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  border-radius: 6px;
}

.close-button:hover:not(:disabled) {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.modal-summary {
  color: #64748b;
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.summary-card {
  padding: 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.summary-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 0.375rem;
}

.summary-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.confirm-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.confirm-list li {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 0.875rem;
  color: #334155;
}

.modal-footer {
  padding: 1.25rem 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
