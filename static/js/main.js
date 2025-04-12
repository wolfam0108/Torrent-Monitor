const socket = io();

socket.on('notification', function(data) {
  const toastTemplate = document.getElementById('toast-template');
  const toast = toastTemplate.cloneNode(true);
  toast.classList.add(`bg-${data.type || 'info'}`);
  toast.querySelector('.toast-body').textContent = data.message;
  document.querySelector('.toast-container').appendChild(toast);
  new bootstrap.Toast(toast, { autohide: true, delay: 5000 }).show();
  toast.addEventListener('hidden.bs.toast', () => toast.remove());
});

socket.on('auth_status', function(data) {
  console.log('Получены статусы авторизации:', data);
  updateStatus('qbittorrent', data.qbittorrent);
  updateStatus('kinozal', data.kinozal);
  updateStatus('rutracker', data.rutracker);
});

socket.on('log', function(data) {
  const logs = document.getElementById('logs');
  if (logs) {
    const log = document.createElement('p');
    log.textContent = data.message;
    log.className = data.level === 'ERROR' ? 'text-danger' : 'text-info';
    logs.appendChild(log);
    logs.scrollTop = logs.scrollHeight;
  }
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
      row.classList.add('bg-success');
      statusCell.textContent = data.status;
      actionButtons.forEach(btn => btn.removeAttribute('disabled'));
    } else {
      row.classList.add('bg-warning');
      statusCell.innerHTML = data.total > 0 ? `${spinner}${data.progress}/${data.total}` : `${spinner}${data.status}`;
      actionButtons.forEach(btn => btn.setAttribute('disabled', 'disabled'));
    }
  }
});

function updateStatus(service, statusData) {
  const statusElement = document.getElementById(`${service}-status`);
  const spinnerElement = document.getElementById(`${service}-spinner`);
  if (statusElement && spinnerElement) {
    statusElement.textContent = statusData.status;
    statusElement.className = statusData.status.includes('Ошибка') ? 'text-danger' : 
                             statusData.status.includes('Подключено') || statusData.status.includes('Авторизация успешна') ? 'text-success' : 
                             'text-muted';
    spinnerElement.style.display = statusData.spinner ? 'inline-block' : 'none';
  }
}

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
  document.querySelectorAll('tr[data-url]').forEach(row => {
    resetRow(row);
  });

  document.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      window.location.href = `/delete/${encodeURIComponent(this.dataset.url)}`;
    });
  });

  document.querySelectorAll('.status-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      console.log('Клик по кнопке "Статус"');
      const seriesUrl = this.dataset.url;
      console.log('seriesUrl:', seriesUrl);
      const row = document.querySelector(`tr[data-url="${seriesUrl}"]`);
      if (row) {
        setRowProcessing(row);
      }
      document.getElementById('status-content').innerHTML = '<div class="text-center"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Загрузка...</div>';
      const modal = new bootstrap.Modal(document.getElementById('statusModal'));
      modal.show();

      console.log(`Отправка запроса на /api/status/${encodeURIComponent(seriesUrl)}`);
      fetch(`/api/status/${encodeURIComponent(seriesUrl)}`)
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
              const statusClass = ep.status === 'Скачан' || ep.status.includes('Скачан') ? 'text-success' : 
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
                fetch(`/api/status/${encodeURIComponent(seriesUrl)}`, {
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
            document.getElementById('statusModal').addEventListener('hidden.bs.modal', function() {
              if (row) resetRow(row);
            }, { once: true });
          }
        })
        .catch(error => {
          console.error('Ошибка запроса:', error);
          document.getElementById('status-content').innerHTML = `<p class="text-danger">Ошибка загрузки данных</p>`;
        });
    });
  });

  document.querySelectorAll('.scan-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      console.log('seriesUrl для сканирования:', this.dataset.url);
      const row = document.querySelector(`tr[data-url="${this.dataset.url}"]`);
      if (row) {
        setRowProcessing(row);
      }
      fetch(`/scan_series/${encodeURIComponent(this.dataset.url)}`, { method: 'GET' })
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
      fetch(`/api/toggle_rename/${encodeURIComponent(seriesUrl)}`, {
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

  // Исправление для кнопок toggle-password
  document.querySelectorAll('.toggle-password').forEach(button => {
    button.addEventListener('click', function() {
      const targetId = this.getAttribute('data-target');
      const input = document.getElementById(targetId);
      const icon = this.querySelector('i');
      
      if (input && icon) {
        if (input.type === 'password') {
          input.type = 'text';
          icon.classList.remove('bi-eye');
          icon.classList.add('bi-eye-slash');
        } else {
          input.type = 'password';
          icon.classList.remove('bi-eye-slash');
          icon.classList.add('bi-eye');
        }
      }
    });
  });
});

document.getElementById('series_url').addEventListener('input', function() {
  const seriesUrl = this.value.trim();
  console.log('Введённый URL:', seriesUrl);
  const dynamicFields = document.getElementById('dynamic-fields');
  const preview = document.getElementById('add-status-preview');
  dynamicFields.innerHTML = '';
  preview.innerHTML = '';

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
        console.log('Полученные данные от /api/scan_url:', data);
        if (data.error) {
          showToast(data.error, 'danger');
          this.parentElement.removeChild(spinner);
          return;
        }

        let domain = '';
        try {
          const url = new URL(seriesUrl);
          const hostname = url.hostname;
          console.log('Извлечённый hostname:', hostname);
          const parts = hostname.split('.');
          domain = parts.length >= 2 ? parts[parts.length - 2] : '';
          console.log('Определённый домен:', domain);
        } catch (e) {
          console.error('Ошибка при разборе URL:', e);
          domain = '';
        }

        let fieldsHtml = '';
        document.querySelector('#addSeriesModal .modal-dialog').style.maxWidth = '800px';

        fieldsHtml += `
          <div class="mb-3">
            <label for="save_path">Путь сохранения</label>
            <input type="text" name="save_path" id="save_path" class="form-control" placeholder="Путь сохранения" required>
          </div>
          <div class="mb-3">
            <label for="series_name">Название</label>
        `;

        if (data.names && data.names.length > 1) {
          fieldsHtml += `<select name="series_name" id="series_name" class="form-control" onchange="if(this.value === 'custom') document.getElementById('custom_name').style.display = 'block'; else document.getElementById('custom_name').style.display = 'none';">`;
          data.names.forEach(name => {
            fieldsHtml += `<option value="${name}">${name}</option>`;
          });
          fieldsHtml += `<option value="custom">Ввести своё</option></select>`;
          fieldsHtml += `<input type="text" name="custom_name" id="custom_name" class="form-control mt-2" placeholder="Введите своё название" style="display: none;">`;
        } else {
          fieldsHtml += `<input type="text" name="series_name" id="series_name" class="form-control" value="${data.name || ''}" required>`;
        }
        fieldsHtml += `</div>`;

        fieldsHtml += `
          <div class="mb-3">
            <label for="season">Сезон</label>
            <input type="text" name="season" id="season" class="form-control" placeholder="Сезон (s01)" required>
          </div>
        `;

        if (domain === 'anilibria') {
          console.log('Ветка для Anilibria, quality_options:', data.quality_options);
          if (data.quality_options && data.quality_options.length > 0) {
            fieldsHtml += `
              <div class="mb-3">
                <label for="quality">Качество</label>
                <select name="quality" id="quality" class="form-control">
                  ${data.quality_options.map(opt => `<option value="${opt.quality}">${opt.quality}</option>`).join('')}
                </select>
              </div>
            `;
          } else {
            console.log('quality_options пустой или отсутствует');
          }
          preview.innerHTML = `
            <table class="table">
              <thead><tr><th>Название</th><th>Дата</th><th>ID</th><th>Качество</th><th>Статус</th></tr></thead>
              <tbody>
                ${data.status_data.episodes.map(ep => `
                  <tr>
                    <td>${ep.name}</td>
                    <td>${ep.last_updated || 'Неизвестно'}</td>
                    <td>${ep.torrent_id}</td>
                    <td>${ep.quality || 'N/A'}</td>
                    <td class="${ep.status === 'Скачан' || ep.status.includes('Скачан') ? 'text-success' : ep.status === 'Загружается' ? 'text-warning' : ep.status === 'Ошибка' ? 'text-danger' : 'text-primary'}">${ep.status}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          `;
        } else if (domain === 'astar') {
          preview.innerHTML = `
            <table class="table">
              <thead><tr><th>Название</th><th>Дата</th><th>ID</th><th>Статус</th></tr></thead>
              <tbody>
                ${data.status_data.episodes.map(ep => `
                  <tr>
                    <td>${ep.episode_name}</td>
                    <td>${ep.last_updated || 'Неизвестно'}</td>
                    <td>${ep.torrent_id}</td>
                    <td class="${ep.status === 'Скачан' || ep.status.includes('Скачан') ? 'text-success' : ep.status === 'Загружается' ? 'text-warning' : ep.status === 'Ошибка' ? 'text-danger' : 'text-primary'}">${ep.status}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          `;
        } else {
          console.log('Ветка для других доменов (nnmclub, kinozal, rutracker), domain:', domain);
          preview.innerHTML = `
            <table class="table">
              <thead><tr><th>Название</th><th>Дата</th><th>ID</th><th>Статус</th></tr></thead>
              <tbody>
                ${data.status_data.episodes.map(ep => `
                  <tr>
                    <td>${ep.name}</td>
                    <td>${ep.last_updated || 'Неизвестно'}</td>
                    <td>${ep.torrent_id}</td>
                    <td class="${ep.status === 'Скачан' || ep.status.includes('Скачан') ? 'text-success' : ep.status === 'Загружается' ? 'text-warning' : ep.status === 'Ошибка' ? 'text-danger' : 'text-primary'}">${ep.status}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          `;
        }

        dynamicFields.innerHTML = fieldsHtml;
        document.getElementById('torrent_ids').value = data.torrent_ids.join(',');
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