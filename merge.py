import sys

# Read index.html
with open('templates/index.html', 'r', encoding='utf-8') as f:
    index_content = f.read()

# Read about.html
with open('templates/about.html', 'r', encoding='utf-8') as f:
    about_content = f.read()

# Extract the container from about.html
start_tag = '<div class="container">'
end_tag = '<!-- Footer -->'
container_start = about_content.find(start_tag)
container_end = about_content.find(end_tag)

if container_start != -1 and container_end != -1:
    about_section = about_content[container_start:container_end]
    script_tag = '<script>'
    container_end2 = about_content.rfind(script_tag, container_start)
    if container_end2 != -1:
        about_section = about_content[container_start:container_end2].strip()

# Make body scrollable
index_content = index_content.replace('body { margin: 0; overflow: hidden; background: #0b1121; }', 'body { margin: 0; overflow-y: auto; overflow-x: hidden; background: #0b1121; }')
index_content = index_content.replace('.welcomeScreen { position: relative; z-index: 1; }', '.welcomeScreen { position: relative; z-index: 1; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; }')

# Include about.css in index.html head
head_closing_tag = '</head>'
css_link = '<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'css/about.css\') }}">'
if css_link not in index_content:
    index_content = index_content.replace(head_closing_tag, f'    {css_link}\n{head_closing_tag}')

# Insert about_section
if '<div class="container">' not in index_content:
    insert_pos = index_content.rfind('<script>')
    if insert_pos != -1:
        # Remove the pill-nav container from the about section since it's now on the home page
        # We can just leave it or remove it using string replacement.
        new_index = index_content[:insert_pos] + '\n\n    <!-- ABOUT SECTION -->\n    <div style="padding-top: 100px;"></div>\n    ' + about_section + '\n\n    ' + index_content[insert_pos:]
        with open('templates/index.html', 'w', encoding='utf-8') as f:
            f.write(new_index)
        print('Successfully merged.')
