from flask import Blueprint, render_template, request, jsonify, send_file, session, redirect, url_for
import json
import io
import yaml
import csv
import toml
import configparser
import xmltodict
import re
import requests
from flask import Flask, request, jsonify
from dicttoxml import dicttoxml
from extensions import db
from models import *

json_bp = Blueprint('json_formatter', __name__)

@json_bp.route('/json_formatter', methods=['GET', 'POST'])
def json_formatter():
    if 'username' not in session:
        return redirect(url_for('home'))

    current_user = User.query.filter_by(username=session['username']).first()

    if request.method == 'POST':
        action = request.form.get('action')
        convert_from = request.form.get('convert_from')
        convert_to = request.form.get('convert_to')
        input_method = request.form.get('input_method', 'text')

        if input_method == 'file':
            if 'file' not in request.files:
                return jsonify({'status': 'error', 'message': 'No file uploaded'})
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'status': 'error', 'message': 'No file selected'})
            
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > 5 * 1024 * 1024:  # 5MB
                return jsonify({'status': 'error', 'message': 'File too large. Maximum size is 5MB.'})
            
            try:
                raw_input = file.read().decode('utf-8')
            except UnicodeDecodeError:
                return jsonify({'status': 'error', 'message': 'File encoding error. Please use UTF-8 encoding.'})
            
            if not convert_from:
                filename = file.filename.lower()
                if filename.endswith('.json'):
                    convert_from = 'json'
                elif filename.endswith(('.yaml', '.yml')):
                    convert_from = 'yaml'
                elif filename.endswith('.csv'):
                    convert_from = 'csv'
                elif filename.endswith('.toml'):
                    convert_from = 'toml'
                elif filename.endswith('.ini'):
                    convert_from = 'ini'
                elif filename.endswith('.xml'):
                    convert_from = 'xml'
        else:
            raw_input = request.form.get('raw_json', '').strip()

        try:
            if action in ('format', 'minify', 'download'):
                try:
                    parsed = json.loads(raw_input)
                except Exception as e:
                    return jsonify({'status': 'error', 'message': f'Invalid JSON: {str(e)}'})

                if action == 'format':
                    pretty = json.dumps(parsed, indent=4)
                    return jsonify({'status': 'success', 'formatted': pretty})

                if action == 'minify':
                    minified = json.dumps(parsed, separators=(',', ':'))
                    return jsonify({'status': 'success', 'formatted': minified})

                if action == 'download':
                    if current_user.points < 2:
                        return jsonify({'status': 'error', 'message': 'Not enough points to download.'})
                    formatted = json.dumps(parsed, indent=4)
                    file_obj = io.BytesIO(formatted.encode())
                    current_user.points -= 2
                    db.session.commit()
                    return send_file(file_obj, download_name='formatted.json', as_attachment=True, mimetype='application/json')

                if action == 'download_converted':
                    if current_user.points < 3:
                        return jsonify({'status': 'error', 'message': 'Not enough points to download converted file.'})
                    
                    return jsonify({'status': 'error', 'message': 'Please use Convert first, then Download Converted.'})

            elif action == 'convert':
                try:
                    if convert_from == 'json' or not convert_from:
                        parsed = json.loads(raw_input)
                    elif convert_from == 'yaml':
                        parsed = yaml.safe_load(raw_input)
                    elif convert_from == 'xml':
                        parsed = xmltodict.parse(raw_input)
                    elif convert_from == 'csv':
                        f = io.StringIO(raw_input)
                        reader = csv.DictReader(f)
                        parsed = list(reader)
                    elif convert_from == 'toml':
                        parsed = toml.loads(raw_input)
                    elif convert_from == 'ini':
                        cp = configparser.ConfigParser()
                        cp.read_string(raw_input)
                        parsed = {s: dict(cp[s]) for s in cp.sections()}
                        if cp.defaults():
                            parsed['DEFAULT'] = dict(cp.defaults())
                    else:
                        return jsonify({'status': 'error', 'message': f'Unsupported input format: {convert_from}'})
                except Exception as e:
                    return jsonify({'status': 'error', 'message': f'Error parsing {convert_from}: {str(e)}'})

                try:
                    if convert_to == 'json' or not convert_to:
                        converted = json.dumps(parsed, indent=4)
                    elif convert_to == 'yaml':
                        converted = yaml.dump(parsed, sort_keys=False)
                    elif convert_to == 'xml':
                        xml_bytes = dicttoxml(parsed, custom_root='root', attr_type=False)
                        converted = xml_bytes.decode()
                    elif convert_to == 'csv':
                        if isinstance(parsed, dict):
                            parsed_list = [parsed]
                        else:
                            parsed_list = parsed
                        if isinstance(parsed_list, list) and parsed_list and isinstance(parsed_list[0], dict):
                            output = io.StringIO()
                            writer = csv.DictWriter(output, fieldnames=parsed_list[0].keys())
                            writer.writeheader()
                            writer.writerows(parsed_list)
                            converted = output.getvalue()
                        else:
                            return jsonify({'status': 'error', 'message': 'CSV conversion supports list of objects/dicts.'})
                    elif convert_to == 'toml':
                        converted = toml.dumps(parsed)
                    elif convert_to == 'ini':
                        if isinstance(parsed, dict):
                            cp = configparser.ConfigParser()
                            cp['DEFAULT'] = {k: str(v) for k, v in parsed.items()}
                            output = io.StringIO()
                            cp.write(output)
                            converted = output.getvalue()
                        else:
                            return jsonify({'status': 'error', 'message': 'INI conversion requires a flat dict.'})
                    else:
                        return jsonify({'status': 'error', 'message': f'Unsupported output format: {convert_to}'})
                except Exception as e:
                    return jsonify({'status': 'error', 'message': f'Error converting to {convert_to}: {str(e)}'})

                if action == 'download_converted':
                    if current_user.points < 3:
                        return jsonify({'status': 'error', 'message': 'Not enough points to download converted file.'})
                    
                    file_extensions = {
                        'json': '.json',
                        'yaml': '.yaml',
                        'xml': '.xml',
                        'csv': '.csv',
                        'toml': '.toml',
                        'ini': '.ini'
                    }
                    ext = file_extensions.get(convert_to, '.txt')
                    
                    file_obj = io.BytesIO(converted.encode())
                    current_user.points -= 3
                    db.session.commit()
                    
                    return send_file(file_obj, download_name=f'converted{ext}', as_attachment=True, mimetype='text/plain')
                
                return jsonify({'status': 'success', 'formatted': converted})

            else:
                return jsonify({'status': 'error', 'message': 'No action specified.'})

        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Unexpected error: {str(e)}'})

    return render_template('tools/json_formatter.html', points=current_user.points)


@json_bp.route("/regex", methods=["GET", "POST"])
def regex():
    if 'username' not in session:
        return redirect(url_for('home'))

    if request.method == "POST":
        pattern = request.form.get("pattern", "")
        test_string = request.form.get("test_string", "")

        try:
            regex = re.compile(pattern)
            matches = regex.findall(test_string)
            return jsonify({
                "status": "success",
                "matches": matches
            })
        except re.error as e:
            return jsonify({
                "status": "error",
                "message": f"Invalid regex: {str(e)}"
            })

    return render_template("tools/regex.html")


@json_bp.route("/run_code", methods=["GET", "POST"])
def run_code():
    if 'username' not in session:
        return redirect(url_for('home'))

    if request.method == "POST":
        data = request.get_json()
        language = data.get("language")
        code = data.get("code")

        payload = {
            "language": language,
            "version": "*",
            "files": [{"name": "main", "content": code}]
        }

        response = requests.post("https://emkc.org/api/v2/piston/execute", json=payload)
        result = response.json()

        return jsonify({
            "output": result.get("run", {}).get("stdout", ""),
            "error": result.get("run", {}).get("stderr", "")
        })

    return render_template("tools/run_code.html")

