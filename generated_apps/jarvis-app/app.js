const output = document.querySelector('#output');
document.querySelector('#action').addEventListener('click', () => {
  output.textContent = [
    'Diagnostic complete.',
    `Timestamp: ${new Date().toLocaleString()}`,
    'Status: prototype ready'
  ].join('\n');
});
