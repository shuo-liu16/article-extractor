import os
import json
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from extractor import extract_by_paragraphs
from utils.excel_export import export_vocab_to_excel

# 加载环境变量
load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract_words():
    """处理词汇提取请求"""
    try:
        # 获取表单数据
        data = request.get_json()
        article = data.get('article', '')
        difficulty = data.get('difficulty', 'medium')
        
        if not article:
            return jsonify({'error': '文章内容不能为空！'}), 400
        
        # 调用词汇提取函数
        vocab_list = extract_by_paragraphs(article, difficulty)
        
        return jsonify({
            'success': True,
            'vocabulary': vocab_list,
            'count': len(vocab_list)
        })
        
    except Exception as e:
        return jsonify({'error': f'提取失败: {str(e)}'}), 500

@app.route('/export', methods=['POST'])
def export_excel():
    """导出Excel文件"""
    try:
        data = request.get_json()
        vocab_list = data.get('vocabulary', [])
        
        if not vocab_list:
            return jsonify({'error': '没有可导出的词汇数据'}), 400
        
        # 导出Excel
        filepath = export_vocab_to_excel(vocab_list)
        
        if not filepath:
            return jsonify({'error': 'Excel文件生成失败'}), 500
        
        # 从文件路径中提取文件名
        filename = os.path.basename(filepath)
        
        return jsonify({
            'success': True,
            'download_url': f'/download/{filename}'
        })
        
    except Exception as e:
        return jsonify({'error': f'导出失败: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """提供文件下载"""
    try:
        filepath = os.path.join('exports', filename)
        
        # 检查文件是否存在
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在或已过期'}), 404
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({'error': f'下载失败: {str(e)}'}), 500

if __name__ == '__main__':
    # 创建导出目录
    os.makedirs('exports', exist_ok=True)
    app.run(debug=True, port=5000)