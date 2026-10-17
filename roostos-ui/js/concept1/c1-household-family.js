// Concept 1: Household Hub - Family & People Management (Compliant with AGENTS.md)
import { store } from '../state.js';

export function renderHouseholdFamily(container) {
    const people = store.data.people;

    const renderRows = () => {
        if (people.length === 0) {
            return `<tr><td colspan="7" style="text-align:center; padding: 32px; color: var(--text-muted);">No family members registered yet. Click "+ Add Person" above to create one.</td></tr>`;
        }
        return people.map(p => `
            <tr id="person-row-${p.id}">
                <td><strong>${p.avatar} ${p.name}</strong></td>
                <td><span class="badge badge-neutral">${p.role}</span></td>
                <td>${p.screentimeLimit > 0 ? `${p.screentimeLimit} mins/day` : 'Unlimited'}</td>
                <td>${p.bedtimeStart} - ${p.bedtimeEnd}</td>
                <td><span class="badge badge-info">${p.filterLevel}</span></td>
                <td>
                    <span class="badge ${p.bedtimeActive ? 'badge-danger' : 'badge-success'}">
                        ${p.bedtimeActive ? 'Bedtime Active' : 'Normal'}
                    </span>
                </td>
                <td>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn btn-secondary btn-sm edit-person-btn" data-id="${p.id}">Edit</button>
                        <button class="btn btn-danger btn-sm delete-person-btn" data-id="${p.id}">Delete</button>
                    </div>
                </td>
            </tr>
        `).join('');
    };

    container.innerHTML = `
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">👨‍👩‍👧‍👦 Family Profiles & Parental Controls</h3>
                    <p class="card-subtitle">Manage screen time quotas, sleep schedules, and content filters per person</p>
                </div>
            </div>

            <!-- Top Add Button per AGENTS.md -->
            <div class="table-action-bar">
                <span style="font-size: 13px; color: var(--text-muted); font-weight: 500;">Household Members (${people.length})</span>
                <button class="btn btn-primary btn-sm add-person-btn" data-position="top">+ Add Person</button>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="people-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Role</th>
                            <th>Daily Limit</th>
                            <th>Bedtime Window</th>
                            <th>Filter Level</th>
                            <th>Current State</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="people-tbody">
                        ${renderRows()}
                    </tbody>
                </table>
            </div>

            <!-- Bottom Add Button per AGENTS.md -->
            <div class="table-action-bar" style="margin-top: 12px;">
                <span></span>
                <button class="btn btn-primary btn-sm add-person-btn" data-position="bottom">+ Add Person</button>
            </div>
        </div>
    `;

    const tbody = container.querySelector('#people-tbody');

    const getFormFields = (p = {}) => `
        <td><input type="text" class="inline-input" id="inp-person-name" value="${p.name || ''}" placeholder="e.g. Grandma"></td>
        <td>
            <select class="inline-select" id="inp-person-role">
                <option value="member" ${p.role === 'member' ? 'selected' : ''}>Member</option>
                <option value="kid" ${p.role === 'kid' ? 'selected' : ''}>Kid</option>
                <option value="parent" ${p.role === 'parent' ? 'selected' : ''}>Parent</option>
            </select>
        </td>
        <td><input type="number" class="inline-input" id="inp-person-limit" value="${p.screentimeLimit ?? 120}" placeholder="Minutes"></td>
        <td>
            <div style="display: flex; gap: 4px;">
                <input type="time" class="inline-input" id="inp-person-bed-start" value="${p.bedtimeStart || '21:00'}">
                <input type="time" class="inline-input" id="inp-person-bed-end" value="${p.bedtimeEnd || '06:30'}">
            </div>
        </td>
        <td>
            <select class="inline-select" id="inp-person-filter">
                <option value="Standard" ${p.filterLevel === 'Standard' ? 'selected' : ''}>Standard</option>
                <option value="SafeSearch + AdBlock" ${p.filterLevel === 'SafeSearch + AdBlock' ? 'selected' : ''}>SafeSearch + AdBlock</option>
                <option value="Strict Kids" ${p.filterLevel === 'Strict Kids' ? 'selected' : ''}>Strict Kids</option>
            </select>
        </td>
        <td><span class="badge badge-neutral">Draft</span></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-btn">Cancel</button>
            </div>
        </td>
    `;

    // Inline Add Row per AGENTS.md
    container.querySelectorAll('.add-person-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelector('.inline-add-row')?.remove();
            const tr = document.createElement('tr');
            tr.className = 'inline-add-row';
            tr.innerHTML = getFormFields();

            if (btn.dataset.position === 'top') {
                tbody.prepend(tr);
            } else {
                tbody.append(tr);
            }

            tr.querySelector('.cancel-btn').onclick = () => tr.remove();
            tr.querySelector('.save-btn').onclick = () => {
                const name = tr.querySelector('#inp-person-name').value.trim();
                if (!name) return alert('Please enter a name');
                store.addPerson({
                    id: name.toLowerCase().replace(/[^a-z0-9]/g, '_'),
                    name,
                    role: tr.querySelector('#inp-person-role').value,
                    screentimeLimit: Number(tr.querySelector('#inp-person-limit').value),
                    bedtimeStart: tr.querySelector('#inp-person-bed-start').value,
                    bedtimeEnd: tr.querySelector('#inp-person-bed-end').value,
                    filterLevel: tr.querySelector('#inp-person-filter').value
                });
            };
        });
    });

    // Inline Edit Row per AGENTS.md
    tbody.addEventListener('click', (e) => {
        const editBtn = e.target.closest('.edit-person-btn');
        const deleteBtn = e.target.closest('.delete-person-btn');

        if (editBtn) {
            const id = editBtn.dataset.id;
            const p = store.data.people.find(x => x.id === id);
            if (!p) return;

            const existingRow = container.querySelector(`#person-row-${id}`);
            if (!existingRow) return;

            const tr = document.createElement('tr');
            tr.className = 'inline-edit-row';
            tr.id = `person-row-${id}`;
            tr.innerHTML = getFormFields(p);

            existingRow.replaceWith(tr);

            tr.querySelector('.cancel-btn').onclick = () => renderHouseholdFamily(container);
            tr.querySelector('.save-btn').onclick = () => {
                store.updatePerson(id, {
                    name: tr.querySelector('#inp-person-name').value.trim(),
                    role: tr.querySelector('#inp-person-role').value,
                    screentimeLimit: Number(tr.querySelector('#inp-person-limit').value),
                    bedtimeStart: tr.querySelector('#inp-person-bed-start').value,
                    bedtimeEnd: tr.querySelector('#inp-person-bed-end').value,
                    filterLevel: tr.querySelector('#inp-person-filter').value
                });
            };
        }

        if (deleteBtn) {
            if (confirm('Delete this family member profile?')) {
                store.deletePerson(deleteBtn.dataset.id);
            }
        }
    });
}
