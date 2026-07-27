document.getElementById('tx-date').value = new Date().toISOString().split('T')[0];
initContractorCombobox();
fetchInitialData();
