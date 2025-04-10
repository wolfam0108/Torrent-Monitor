const socket = io();

socket.on('log', function(data) {
    const logs = document.getElementById('logs');
    const log = document.createElement('p');
    log.textContent = data.message;
    log.className = data.level === 'ERROR' ? 'text-danger' : 'text-info';
    logs.appendChild(log);
    logs.scrollTop = logs.scrollHeight;
});

socket.on('notification', function(data) {
    const toastTemplate = document.getElementById('toast-template');
    const toast = toastTemplate.cloneNode(true);
    toast.classList.add(`bg-${data.type || 'info'}`);
    toast.querySelector('.toast-body').textContent = data.message;
    document.querySelector('.toast-container').appendChild(toast);
    new bootstrap.Toast(toast, { autohide: true, delay: 5000 }).show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
});

socket.on('status_update', function(data) {
    console.log('Получено status_update:', data);
    const row = document.querySelector(`tr[data-url="${data.series_url}"]`);
    if (row) {
        const statusCell = row.querySelector('.status');
        const actionButtons = row.querySelectorAll('.actions .btn');
        row.classList.remove('bg-warning', 'bg-success', 'bg-danger');
        const spinner = '<span class="spinner-grow text-success" role="status" aria-hidden="true"></span> ';
        if (data.status === 'Завершено') {
            row.classList.add('bg-success');
            statusCell.textContent = 'Готов';
            actionButtons.forEach(btn => btn.removeAttribute('disabled'));
        } else if (data.status.startsWith('Ошибка')) {
            row.classList.add('bg-danger');
            statusCell.textContent = data.status;
            actionButtons.forEach(btn => btn.removeAttribute('disabled'));
        } else if (data.status === 'Переименование завершено') {
            row.classList.add('bg-success'); // Успешное завершение переименования
            statusCell.textContent = data.status;
            actionButtons.forEach(btn => btn.removeAttribute('disabled'));
        } else {
            row.classList.add('bg-warning');
            statusCell.innerHTML = data.total > 0 ? `${spinner}${data.progress}/${data.total}` : `${spinner}${data.status}`;
            actionButtons.forEach(btn => btn.setAttribute('disabled', 'disabled'));
        }
    }
});

socket.on('qb_status_update', function(data) {
    const qbStatus = document.querySelector('.qb-status');
    if (qbStatus) {
        qbStatus.textContent = data.message;
        qbStatus.className = `qb-status ${data.status ? 'text-success' : 'text-danger'}`;
    }
});

function setRowProcessing(row) {
    row.classList.remove('bg-success', 'bg-danger');
    row.classList.add('bg-warning');
    const statusCell = row.querySelector('.status');
    statusCell.innerHTML = '<span class="spinner-grow text-success" role="status" aria-hidden="true"></span> В процессе';
    const actionButtons = row.querySelectorAll('.actions .btn');
    actionButtons.forEach(btn => btn.setAttribute('disabled', 'disabled'));
}

function resetRow(row) {
    row.classList.remove('bg-warning', 'bg-success', 'bg-danger');
    const statusCell = row.querySelector('.status');
    statusCell.textContent = 'Ожидание';
    const actionButtons = row.querySelectorAll('.actions .btn');
    actionButtons.forEach(btn => btn.removeAttribute('disabled'));
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('tr[data-url]').forEach(row => resetRow(row));
});

document.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        window.location.href = `/delete/${this.dataset.url}`;
    });
});

document.querySelectorAll('.status-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        console.log('Клик по кнопке "Статус"');
        const seriesUrl = this.dataset.url;
        const row = document.querySelector(`tr[data-url="${seriesUrl}"]`);
        if (row) {
            setRowProcessing(row);
        }
        document.getElementById('status-content').innerHTML = '<div class="text-center"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Загрузка...</div>';
        const modal = new bootstrap.Modal(document.getElementById('statusModal'));
        modal.show();

        console.log(`Отправка запроса на /api/status/${seriesUrl}`);
        fetch(`/api/status/${seriesUrl}`)
            .then(response => {
                console.log('Ответ от сервера получен');
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    document.getElementById('status-content').innerHTML = `<p class="text-danger">${data.error}</p>`;
                } else {
                    let html = `<p>Всего: ${data.status_data.total}</p><p>Скачано: <span class="text-success">${data.status_data.downloaded}</span></p><p>Новых: <span class="text-primary">${data.status_data.new}</span></p>`;
                    html += '<table class="table"><thead><tr><th>Название</th><th>Дата</th><th>ID</th><th>Статус</th></tr></thead><tbody>';
                    data.status_data.episodes.forEach(ep => {
                        const statusClass = ep.status === 'Скачан' || ep.status === 'Скачан (Пауза)' || ep.status === 'Скачан (В очереди)' ? 'text-success' : 
                                           ep.status === 'Загружается' ? 'text-warning' : 
                                           ep.status === 'Ошибка' ? 'text-danger' : 'text-primary';
                        html += `<tr><td>${ep.name}</td><td>${ep.date}</td><td>${ep.torrent_id}</td><td class="${statusClass}">${ep.status}</td></tr>`;
                    });
                    html += '</tbody></table>';
                    if (data.can_rename) {
                        html += '<h6>Предпросмотр переименования</h6><table class="table"><thead><tr><th>Текущее имя</th><th>Новое имя</th></tr></thead><tbody>';
                        data.rename_preview.forEach(item => {
                            html += `<tr><td>${item.current_name}</td><td>${item.new_name}</td></tr>`;
                        });
                        html += '</tbody></table>';
                        html += '<form id="rename-form"><div class="mb-3"><label>Название сериала</label><input type="text" name="series_name" class="form-control" value="' + data.series_data.series_name + '" required></div>';
                        html += '<div class="mb-3"><label>Сезон</label><input type="text" name="season" class="form-control" value="' + data.series_data.season + '" required></div>';
                        html += '<button type="submit" class="btn btn-success">Принять</button></form>';
                    }
                    document.getElementById('status-content').innerHTML = html;
                    if (data.can_rename) {
                        document.getElementById('rename-form').addEventListener('submit', function(e) {
                            e.preventDefault();
                            const formData = new FormData(this);
                            fetch(`/api/status/${seriesUrl}`, {
                                method: 'POST',
                                body: formData
                            })
                            .then(response => response.json())
                            .then(data => {
                                if (data.error) {
                                    showToast(data.error, 'danger');
                                } else {
                                    showToast(data.message, 'success');
                                    bootstrap.Modal.getInstance(document.getElementById('statusModal')).hide();
                                }
                            })
                            .catch(error => showToast('Ошибка при переименовании', 'danger'));
                        });
                    }
                }
                document.getElementById('statusModal').addEventListener('hidden.bs.modal', function() {
                    if (row) resetRow(row);
                }, { once: true });
            })
            .catch(error => {
                console.error('Ошибка запроса:', error);
                document.getElementById('status-content').innerHTML = `<p class="text-danger">Ошибка загрузки данных</p>`;
            });
    });
});

document.querySelectorAll('.scan-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const seriesUrl = this.dataset.url;
        const row = document.querySelector(`tr[data-url="${seriesUrl}"]`);
        if (row) {
            setRowProcessing(row);
        }
        fetch(`/scan_series/${seriesUrl}`, { method: 'GET' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'started') {
                    showToast('Сканирование запущено', 'info');
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
                showToast('Произошла ошибка при сканировании', 'danger');
                if (row) resetRow(row);
            });
    });
});

document.querySelectorAll('.rename-toggle').forEach(toggle => {
    toggle.addEventListener('change', function() {
        const seriesUrl = this.dataset.url;
        fetch(`/api/toggle_rename/${seriesUrl}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: this.checked })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
                this.checked = !this.checked;
            } else {
                showToast(`Авто-переименование ${this.checked ? 'включено' : 'выключено'}`, 'success');
            }
        })
        .catch(error => {
            console.error('Ошибка при переключении авто-переименования:', error);
            showToast('Ошибка при сохранении настроек', 'danger');
            this.checked = !this.checked;
        });
    });
});

document.getElementById('series_url').addEventListener('input', function() {
    const seriesUrl = this.value.trim();
    if (seriesUrl) {
        const spinner = document.createElement('span');
        spinner.className = 'spinner-border spinner-border-sm ms-2';
        this.parentElement.appendChild(spinner);
        fetch('/api/scan_url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ series_url: seriesUrl })
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById('series_name').value = data.name || '';
            const qualitySelect = document.getElementById('quality');
            qualitySelect.innerHTML = '';
            data.quality_options.forEach(option => {
                const opt = document.createElement('option');
                opt.value = option.quality;
                opt.textContent = option.quality;
                qualitySelect.appendChild(opt);
            });
            document.getElementById('torrent_ids').value = data.torrent_ids.join(',');
            let html = '<table class="table"><thead><tr><th>Название</th><th>ID</th><th>Статус</th></tr></thead><tbody>';
            data.status_data.episodes.forEach(ep => {
                const statusClass = ep.status === 'Скачан' || ep.status === 'Скачан (Пауза)' || ep.status === 'Скачан (В очереди)' ? 'text-success' : 
                                   ep.status === 'Загружается' ? 'text-warning' : 
                                   ep.status === 'Ошибка' ? 'text-danger' : 'text-primary';
                html += `<tr><td>${ep.name}</td><td>${ep.torrent_id}</td><td class="${statusClass}">${ep.status}</td></tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('add-status-preview').innerHTML = html;
            this.parentElement.removeChild(spinner);
        })
        .catch(error => {
            console.error('Ошибка сканирования URL:', error);
            showToast('Ошибка при сканировании URL', 'danger');
            this.parentElement.removeChild(spinner);
        });
    }
});

function showToast(message, type) {
    const toastTemplate = document.getElementById('toast-template');
    const toast = toastTemplate.cloneNode(true);
    toast.classList.add(`bg-${type || 'info'}`);
    toast.querySelector('.toast-body').textContent = message;
    document.querySelector('.toast-container').appendChild(toast);
    new bootstrap.Toast(toast, { autohide: true, delay: 5000 }).show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}