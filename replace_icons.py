import re

with open('d:/ITI/GP/newapp/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

icons = {
    'pbix1': '<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"Dashboard\"><path d=\"M4 3h6a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM4 14h6a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2z\" fill=\"currentColor\" opacity=\"0.4\"/><path d=\"M14 11h6a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2zM14 3h6a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2h-6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z\" fill=\"currentColor\"/></svg>',
    
    'rdl1': '<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"Risk\"><path d=\"M12 2l8 3.5v6c0 5.5-3.6 10.1-8 11.5-4.4-1.4-8-6-8-11.5v-6L12 2z\" fill=\"currentColor\" opacity=\"0.3\"/><path d=\"M12 16a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm0-8a1.5 1.5 0 0 0-1.5 1.5v3a1.5 1.5 0 0 0 3 0v-3A1.5 1.5 0 0 0 12 8z\" fill=\"currentColor\"/></svg>',
    
    'rdl2': '<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"Forecasting\"><path d=\"M3 3a1 1 0 0 0-2 0v18a1 1 0 0 0 1 1h18a1 1 0 0 0 0-2H3V3z\" fill=\"currentColor\"/><path d=\"M21.7 6.3l-6 6a1 1 0 0 1-1.4 0l-3.3-3.3-4.3 4.3a1 1 0 1 1-1.4-1.4l5-5a1 1 0 0 1 1.4 0l3.3 3.3 5.3-5.3a1 1 0 1 1 1.4 1.4z\" fill=\"currentColor\" opacity=\"0.4\"/><circle cx=\"21\" cy=\"6\" r=\"2.5\" fill=\"currentColor\"/><circle cx=\"15\" cy=\"12\" r=\"2.5\" fill=\"currentColor\"/><circle cx=\"11\" cy=\"8\" r=\"2.5\" fill=\"currentColor\"/></svg>',
    
    'rdl3': '<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"Executive\"><path d=\"M20 6h-4V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2zM10 4h4v2h-4V4z\" fill=\"currentColor\" opacity=\"0.3\"/><path d=\"M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z\" fill=\"currentColor\"/></svg>',
    
    'rdl4': '<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"Supply Chain\"><path d=\"M1 5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V5z\" fill=\"currentColor\" opacity=\"0.3\"/><path d=\"M16 7h3.5l3.5 4.5V17a2 2 0 0 1-2 2h-5V7z\" fill=\"currentColor\" opacity=\"0.15\"/><path d=\"M6 16a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zm11 0a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM16 11h4l-2.5-3H16v3z\" fill=\"currentColor\"/></svg>',
    
    'rdl5': '<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"Currency\"><path d=\"M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zM12 20c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z\" fill=\"currentColor\" opacity=\"0.3\"/><path d=\"M12.5 17v-1.2c1.7-.2 3.1-1.3 3.5-3h-2.1c-.2.7-.9 1.2-1.9 1.2-1.4 0-2.3-.9-2.3-2 0-1.1.9-1.9 2.5-2.2l1.6-.3c2.4-.4 3.7-1.8 3.7-3.8 0-1.8-1.4-3.2-3.5-3.5V1h-2v1.2c-1.6.3-2.9 1.4-3.3 3h2.1c.2-.6.9-1.1 1.8-1.1 1.2 0 2.1.8 2.1 1.8 0 1.1-.9 1.8-2.5 2.1l-1.6.3c-2.4.4-3.7 1.8-3.7 3.8 0 1.9 1.5 3.3 3.6 3.6V17h2z\" fill=\"currentColor\"/></svg>',
    
    'rdl6': '<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"Trade Partners\"><path d=\"M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3z\" fill=\"currentColor\"/><path d=\"M16 13c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5z\" fill=\"currentColor\" opacity=\"0.4\"/><path d=\"M8 13c-.25 0-.5.01-.76.04C5.12 13.43 3 15.02 3 17v2h4.5v-2.5c0-1.1.42-2.32 1.3-3.08-.26-.27-.55-.42-.8-.42z\" fill=\"currentColor\"/></svg>'
}

for rid, svg_str in icons.items():
    pattern = r'(data-report=[\'\"]' + rid + r'[\'\"].*?(?:<span class=\"reportIcon[^>]*>|<span class=\"mobileReportIcon[^>]*>|<span class=\"dockIcon\">))\s*<svg[^>]*>.*?</svg>'
    content = re.sub(pattern, r'\g<1>' + svg_str, content, flags=re.DOTALL)

with open('d:/ITI/GP/newapp/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
