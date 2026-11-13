(function () {
  const MAX_FILE_SIZE = 100 * 1024 * 1024;
  const ORDERS_KEY = 'layerline.orders';
  const ESTIMATE_KEY = 'layerline.estimate';
  const fileInput = document.createElement('input');
  let selectedFile = null;

  fileInput.id = 'model-file-input';
  fileInput.type = 'file';
  fileInput.accept = '.stl,.obj';
  fileInput.hidden = true;
  fileInput.setAttribute('aria-label', 'Выберите модель STL или OBJ');
  document.body.appendChild(fileInput);

  const feedback = document.querySelector('[data-feedback]');
  const orderButton = document.querySelector('[data-action="place-order"]');
  const fileName = document.querySelector('[data-file-name]');
  const fileMeta = document.querySelector('[data-file-meta]');
  const quoteFileName = document.querySelector('[data-quote-filename]');
  const removeButton = document.querySelector('[data-action="remove-file"]');
  const dropzone = document.querySelector('[data-dropzone]');
  const orderItems = document.querySelector('[data-order-items]');

  function showMessage(message, isError) {
    if (!feedback) return;
    feedback.textContent = message;
    feedback.style.color = isError ? '#FF8F94' : '#A8B1BC';
  }

  function displaySize(bytes) {
    return (bytes / (1024 * 1024)).toFixed(1).replace('.', ',') + ' МБ';
  }

  function selectFile(file) {
    if (!file) return;
    const extension = file.name.split('.').pop().toLowerCase();
    if (extension !== 'stl' && extension !== 'obj') {
      showMessage('Поддерживаются только файлы STL и OBJ.', true);
      return;
    }
    if (file.size === 0 || file.size > MAX_FILE_SIZE) {
      showMessage(file.size === 0
        ? 'Файл пустой. Выберите STL или OBJ с данными модели.'
        : 'Размер файла превышает ограничение 100 МБ.', true);
      return;
    }

    selectedFile = file;
    if (fileName) fileName.textContent = file.name;
    if (fileMeta) fileMeta.textContent = extension.toUpperCase() + ' · ' + displaySize(file.size);
    if (quoteFileName) quoteFileName.textContent = file.name;
    if (removeButton) removeButton.disabled = false;
    if (orderButton) orderButton.disabled = false;
    showMessage('Файл выбран локально (' + displaySize(file.size) + '). Он не отправляется на сервер.', false);
  }

  function getEstimate() {
    const total = document.querySelector('[aria-labelledby="price-title"] [aria-live="polite"]');
    const dimensions = document.querySelector('[aria-labelledby="price-title"] p span:last-child');
    const selectedMaterial = document.querySelector('.mat[aria-pressed="true"]');
    const quantity = document.querySelector('[aria-labelledby="material-title"] span[aria-live="polite"]');
    return {
      fileName: selectedFile && selectedFile.name,
      fileSize: selectedFile && selectedFile.size,
      dimensions: dimensions ? dimensions.textContent.trim() : '',
      material: selectedMaterial ? selectedMaterial.innerText.trim().split('\n')[0] : '',
      quantity: quantity ? Number(quantity.textContent.trim()) : 1,
      total: total ? total.textContent.trim() : '',
      createdAt: new Date().toISOString()
    };
  }

  function readStoredOrders() {
    const stored = localStorage.getItem(ORDERS_KEY);
    if (!stored) return [];
    const orders = JSON.parse(stored);
    if (!Array.isArray(orders)) throw new Error('Список заказов в браузере имеет неверный формат.');
    return orders;
  }

  function updateOrderCount(count) {
    const orderLink = document.querySelector('.nav[href="#orders"]');
    const badge = orderLink && orderLink.querySelector('span:last-child');
    if (badge) badge.textContent = String(count);
  }

  function renderOrders(orders) {
    if (!orderItems) return;
    orderItems.replaceChildren();
    if (orders.length === 0) {
      const empty = document.createElement('li');
      empty.className = 'portal-copy';
      empty.textContent = 'Пока нет заявок, созданных в этом браузере.';
      orderItems.appendChild(empty);
      return;
    }

    orders.forEach(function (order) {
      const item = document.createElement('li');
      const title = document.createElement('strong');
      const details = document.createElement('p');
      const status = document.createElement('p');
      item.className = 'portal-card';
      title.textContent = 'Заказ ' + order.id + ' · ' + order.fileName;
      details.className = 'portal-copy';
      details.textContent = [order.material, order.dimensions, order.quantity + ' шт.', order.total].filter(Boolean).join(' · ');
      status.className = 'portal-copy';
      status.textContent = order.status;
      item.append(title, details, status);
      orderItems.appendChild(item);
    });
  }

  document.addEventListener('click', function (event) {
    const button = event.target.closest('[data-action]');
    if (!button) return;

    switch (button.dataset.action) {
      case 'choose-file':
        fileInput.click();
        break;
      case 'remove-file':
        selectedFile = null;
        if (fileName) fileName.textContent = 'Файл не выбран';
        if (fileMeta) fileMeta.textContent = 'STL или OBJ · до 100 МБ';
        if (quoteFileName) quoteFileName.textContent = 'файл не выбран';
        if (removeButton) removeButton.disabled = true;
        if (orderButton) orderButton.disabled = true;
        showMessage('Загрузите модель STL или OBJ, чтобы оформить заказ.', false);
        break;
      case 'save-estimate':
        try {
          if (!selectedFile) {
            showMessage('Сначала загрузите модель STL или OBJ.', true);
            return;
          }
          localStorage.setItem(ESTIMATE_KEY, JSON.stringify(getEstimate()));
          showMessage('Расчёт сохранён в этом браузере.', false);
        } catch (error) {
          showMessage('Не удалось сохранить расчёт: ' + error.message, true);
        }
        break;
      case 'place-order':
        try {
          if (!selectedFile) {
            showMessage('Сначала загрузите модель STL или OBJ.', true);
            return;
          }
          const orders = readStoredOrders();
          const order = Object.assign(getEstimate(), {
            id: 'A-' + String(Date.now()).slice(-6),
            status: 'Черновик — ожидает отправки на сервер'
          });
          orders.unshift(order);
          const savedOrders = orders.slice(0, 50);
          localStorage.setItem(ORDERS_KEY, JSON.stringify(savedOrders));
          updateOrderCount(savedOrders.length);
          renderOrders(savedOrders);
          showMessage('Заказ ' + order.id + ' сохранён в этом браузере. Для передачи в производство нужен сервер.', false);
        } catch (error) {
          showMessage('Не удалось сохранить заказ: ' + error.message, true);
        }
        break;
      case 'notifications':
        showMessage('Новых уведомлений нет.', false);
        break;
      default:
        break;
    }
  });

  fileInput.addEventListener('change', function () {
    selectFile(fileInput.files && fileInput.files[0]);
    fileInput.value = '';
  });

  if (dropzone) {
    dropzone.addEventListener('dragover', function (event) {
      event.preventDefault();
      dropzone.classList.add('dragging');
    });
    dropzone.addEventListener('dragleave', function (event) {
      if (!dropzone.contains(event.relatedTarget)) dropzone.classList.remove('dragging');
    });
    dropzone.addEventListener('drop', function (event) {
      event.preventDefault();
      dropzone.classList.remove('dragging');
      const files = event.dataTransfer && event.dataTransfer.files;
      if (files && files.length > 1) {
        showMessage('Загрузите один файл за раз.', true);
      } else if (files && files.length === 1) {
        selectFile(files[0]);
      }
    });
  }

  try {
    const orders = readStoredOrders();
    updateOrderCount(orders.length);
    renderOrders(orders);
  } catch (error) {
    showMessage('Не удалось прочитать сохранённые заказы: ' + error.message, true);
  }
})();
