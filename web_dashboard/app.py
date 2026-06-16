import os
from functools import lru_cache
import subprocess
import requests as r
import re
from flask import Flask, json, render_template, jsonify, request
from modules.format_logs import get_logs
from modules.rule_manager import RuleManager

app = Flask(__name__)

# Runtime data files (rules state, etc.)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
RULES_FILE = os.path.join(DATA_DIR, "rules.json")

def get_extensions_list():
    try:
        result = subprocess.run(['sudo', '-u', 'amir', 'code', '--list-extensions'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        if result.returncode != 0:
            print(f"Error getting extensions: {result.stderr}")
            return "Error getting extensions list"
        data = result.stdout
        return data
    except Exception as e:
        print(f"Exception in get_extensions_list: {str(e)}")
        return f"Error: {str(e)}"

@lru_cache(maxsize=None)
def get_ext_info(ext):
    resp = r.get(f"https://marketplace.visualstudio.com/items?itemName={ext}")
    data = resp.text
    try:
        name = data.split("ux-item-name")[2].split(">")[1].split("<")[0]
    except:
        name = "Not found"
    try:
        author = data.split("ux-item-publisher-link item-banner-focussable-child-item")[1].split(">")[1].split("<")[0]
    except:
        author = "Not found"
    
    try:    
        img = data.split("image-display")[1].split('src="')[1].split('"')[0]
    except:
        img = "Not found"

    # Получаем версию
    try:
        version = data.split('Version</td>')[1].split('">')[1].split('</td>')[0]
    except:
        version = "N/A"

    # Получаем рейтинг
    try:
        rating = data.split('average-rating">')[1].split('</span>')[0].strip()
        rating_count = data.split('rating-count">')[1].split('</span>')[0].strip()
    except:
        rating = "N/A"
        rating_count = "0"

    # Получаем количество установок
    try:
        installs = data.split('installs">')[1].split('</span>')[0].strip()
    except:
        installs = "N/A"

    # Получаем количество загрузок
    try:
        downloads = data.split('downloads">')[1].split('</span>')[0].strip()
    except:
        downloads = "N/A"

    return name, author, img, version, rating, rating_count, installs, downloads

@lru_cache(maxsize=None)
def get_ext_description(ext):
    resp = r.get(f"https://marketplace.visualstudio.com/items?itemName={ext}")
    data = resp.text
    pattern = r'<img src="https:\/\/[^"]+" alt="logo" width="200">'
    try:
        # Получаем полное описание из overview
        overview = data.split('class="overview selected-tab"')[1].split('<div class="itemDetails">')[1].split('<div class="markdown">')[1]
        overview = overview.split('Contact us')[0]
        
        # Удаляем изображение иконки из описания
        if 'logo.png' in overview:
            overview = re.sub(pattern, '', overview)
        
        return "", overview
    except:
        return "Description not found", ""

def search_marketplace_extensions(query):
    url = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"
    session_id = '544d7c84-4822-4f8d-b683-86f71afd4dda'
    
    headers = {
        'Accept': 'application/json;api-version=7.2-preview.1;excludeUrls=true',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
        'Accept-Language': 'en-GB,en;q=0.9',
        'X-TFS-Session': session_id,
        'X-TFS-FedAuthRedirect': 'Suppress',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://marketplace.visualstudio.com',
        'Referer': f'https://marketplace.visualstudio.com/search?term={query}&target=VSCode&category=All%20categories&sortBy=Relevance',
        'Sec-Ch-Ua': '"Not A(Brand";v="8", "Chromium";v="132"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Priority': 'u=1, i'
    }
    
    data = {
        "assetTypes": [
            "Microsoft.VisualStudio.Services.Icons.Default",
            "Microsoft.VisualStudio.Services.Icons.Branding",
            "Microsoft.VisualStudio.Services.Icons.Small"
        ],
        "filters": [{
            "criteria": [
                {"filterType": 8, "value": "Microsoft.VisualStudio.Code"},
                {"filterType": 10, "value": query},
                {"filterType": 12, "value": "37888"}
            ],
            "direction": 2,
            "pageSize": 54,
            "pageNumber": 1,
            "sortBy": 0,
            "sortOrder": 0,
            "pagingToken": None
        }],
        "flags": 870
    }
    
    try:
        response = r.post(url, headers=headers, json=data)
        #print(response.text)
        
        if response.status_code == 200:
            results = response.json().get('results', [])
            extensions = []
            
            if results and len(results) > 0:
                for ext in results[0].get('extensions', []):
                    # Get icon URL from assets
                    icon_url = None
                    if 'versions' in ext and len(ext['versions']) > 0:
                        files = ext['versions'][0].get('files', [])
                        for file in files:
                            if file.get('assetType') == 'Microsoft.VisualStudio.Services.Icons.Small':
                                icon_url = file.get('source')
                                break
                    
                    # Get statistics
                    stats = {stat['statisticName']: stat['value'] for stat in ext.get('statistics', [])}
                    
                    extension = {
                        'id': f"{ext.get('publisher', {}).get('publisherName', '')}.{ext.get('extensionName', '')}",
                        'title': ext.get('displayName', ''),
                        'publisher': ext.get('publisher', {}).get('displayName', ''),
                        'description': ext.get('shortDescription', ''),
                        'icon': icon_url,
                        'installs': stats.get('install', 0),
                        'rating': stats.get('averagerating', 0),
                        'about_url': f"/about/{ext.get('publisher', {}).get('publisherName', '')}.{ext.get('extensionName', '')}"
                    }
                    extensions.append(extension)
            
            return {
                'success': True,
                'query': query,
                'extensions': extensions,
                'total': len(extensions)
            }
        else:
            return {
                'success': False,
                'error': f'Failed to fetch extensions: {response.status_code}',
                'query': query
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'query': query
        }

@app.route('/get_ext_list', methods=['POST'])
def ext_list():
    data = request.get_json()
    extension_name = data.get('extensionName')
    if not extension_name:
        return jsonify({
            'success': False,
            'error': 'Extension name is required',
            'query': None
        })
    
    result = search_marketplace_extensions(extension_name)
    return jsonify(result)

@app.route('/')
def home():
    extensions = get_extensions_list()
    print(extensions)
    extensions = extensions.split("\n")
    extensions_ret = {}
    for ext in extensions:
        data = [get_ext_info(ext)]
        if "Not found" not in data[0]:
            extensions_ret[ext] = data
    return render_template('start.html', extensions=extensions_ret)

@app.route('/search_extension', methods=['POST'])
def search_extension():
    data = request.get_json()
    extension_name = data.get('extensionName')
    if not extension_name:
        return jsonify({'success': False, 'error': 'Extension name is required'})
    
    result = search_marketplace_extensions(extension_name)
    return jsonify(result)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/install_extension/<ext_id>')
def install_extension(ext_id):
    try:
        result = subprocess.run(['code', '--install-extension', ext_id], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, 
                              text=True)
        if result.returncode == 0:
            return jsonify({"success": True, "message": "Extension installed successfully"})
        else:
            return jsonify({"success": False, "message": f"Installation failed: {result.stderr}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/about/<ext>')
def about_ext(ext):
    name, author, img, version, rating, rating_count, installs, downloads = get_ext_info(ext)
    short_description, overview = get_ext_description(ext)
    return render_template('about.html',
                         id=ext, 
                         name=name, 
                         author=author, 
                         img=img, 
                         description=short_description,
                         overview=overview,
                         version=version,
                         rating=rating,
                         rating_count=rating_count,
                         installs=installs,
                         downloads=downloads)

@app.route('/rules')
def rules():
    return render_template('rules.html')

@app.route('/logs')
def logs():
    netw = '\n'.join(get_logs())
    with open("process_info.log", 'r') as f:
        log_data = f.read()
        f.close()
    with open("files_read.log", 'r') as f:
        read_files = f.read()
        f.close()
    with open("files_write.log", 'r') as f:
        write_files = f.read()
        f.close()
    return render_template('logs.html', log_data=log_data, netw=netw, read_files=read_files, write_files=write_files)

@app.route('/get_chart_data', methods=['GET'])
def get_chart_data():
    # Read data from process_info.log
    cpu_data = []
    memory_data = []
    with open('process_info.log', 'r') as f:
        for line in f.read().split("\n"):
            parts = line.split(' ')
            if len(parts) == 2:  # Assuming the format is known
                cpu_data.append(int(float(parts[0])))  # Assuming CPU usage is in the first column
                memory_data.append(int(float(parts[1])))
    return jsonify({'cpu': cpu_data, 'memory': memory_data})

@app.route('/set_rule', methods=['GET'])
def set_rule():
    return render_template("configure_rules.html")


@app.route("/save_data", methods=['POST'])
def save_data():
    data = request.json
    with open(RULES_FILE, "w") as f:
        f.write(json.dumps(data))

    # Применить правила
    rule_manager = RuleManager(rules_file=RULES_FILE)
    rule_manager.apply_rules()

    return "OK"

@app.route('/clear_rules')
def clear_rules():
    with open(RULES_FILE, "w") as f:
        f.write("{}")
    return "OK"

@app.route('/get_saved_rules')
def get_rules():
    with open(RULES_FILE, "r") as f:
        data = f.read()
    return data

@app.route('/guide')
def guide():
    return render_template('guide.html')

@app.route('/check_extension/<ext_id>')
def check_extension(ext_id):
    extensions = get_extensions_list()
    is_installed = ext_id in extensions
    return jsonify({'installed': is_installed})

@app.route('/delete_ext/<ext_id>', methods=['DELETE'])
def delete_extension(ext_id):
    try:
        subprocess.run(['code', '--uninstall-extension', ext_id], check=True)
        return jsonify({'success': True})
    except subprocess.CalledProcessError:
        return jsonify({'success': False}), 500

if __name__ == '__main__':
    app.run(debug=True)
