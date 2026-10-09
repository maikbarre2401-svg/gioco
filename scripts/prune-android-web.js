// Removes the icon fonts the app never uses from the Android web bundle (only Ionicons is used).
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'assets', 'node_modules',
  '@expo', 'vector-icons', 'build', 'vendor', 'react-native-vector-icons', 'Fonts');
if (fs.existsSync(dir)) {
  for (const f of fs.readdirSync(dir)) {
    if (!f.startsWith('Ionicons.')) fs.rmSync(path.join(dir, f));
  }
}
fs.rmSync(path.join(__dirname, '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'metadata.json'), { force: true });
