// Раскладка стенда шаблонов должна существовать до загрузки файлов тестов:
// состав блоков читается из манифестов, а не дублируется в спецификации.
const { execFileSync } = require('child_process');
const path = require('path');

module.exports = async () => {
  const root = path.join(__dirname, '..', '..');
  execFileSync(
    path.join(root, '.venv', 'bin', 'python'),
    [path.join('tests', 'tools', 'template_stand.py'), '--plan-only'],
    { cwd: root, stdio: 'inherit' },
  );
};
