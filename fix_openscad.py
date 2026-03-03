with open('openscad.min.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Убираем import.meta.url
content = content.replace('import.meta.url', '"./"')
# Убираем export default
content = content.replace('\nexport default OpenSCAD;', '')

with open('openscad.min.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed openscad.min.js for classic worker")

