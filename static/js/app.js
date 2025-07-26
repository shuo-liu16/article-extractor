// 全局变量
let currentVocabulary = [];

// 词性映射
const POS_MAP = {
    'n': '名词 (Noun)',
    'v': '动词 (Verb)',
    'adj': '形容词 (Adjective)',
    'adv': '副词 (Adverb)',
    'prep': '介词 (Preposition)',
    'conj': '连词 (Conjunction)',
    'pron': '代词 (Pronoun)',
    'det': '限定词 (Determiner)',
    'int': '感叹词 (Interjection)'
};

// 获取词性全称
function getPosName(posAbbr) {
    return POS_MAP[posAbbr] || '其他词性';
}

// 渲染词汇列表
function renderVocabularyList(vocabList) {
    const container = $('#vocabularyList');
    container.empty();
    
    if (vocabList.length === 0) {
        container.html('<div class="col-12 text-center py-4 text-muted">没有提取到任何词汇</div>');
        return;
    }
    
    vocabList.forEach((item, index) => {
        const posName = getPosName(item.pos);
        const commonUsage = item['common-usage'] || [];
        const usageText = Array.isArray(commonUsage) ? commonUsage.join(' • ') : commonUsage;
        const isPhrase = item.type === 'phrase';
        
        const card = `
        <div class="col-md-6 col-lg-4">
            <div class="vocab-card card mb-3 fade-in" style="animation-delay: ${index * 0.1}s;">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="flex-grow-1">
                            <h5 class="word-header card-title mb-1">${item.word}</h5>
                            <div class="d-flex align-items-center gap-2">
                                <span class="pos-badge badge">${item.pos}</span>
                                <span class="badge ${isPhrase ? 'bg-warning' : 'bg-info'}">${isPhrase ? '词组' : '单词'}</span>
                                <small class="text-muted">${posName}</small>
                            </div>
                        </div>
                        <span class="badge bg-secondary">#${index + 1}</span>
                    </div>
                    
                    <div class="mb-3">
                        <h6 class="text-primary mb-1">
                            <i class="bi bi-translate"></i> 英文释义
                        </h6>
                        <p class="card-text mb-2">${item.definition || '暂无释义'}</p>
                        
                        ${item['definition-ch'] ? `
                        <h6 class="text-success mb-1">
                            <i class="bi bi-chat-quote"></i> 中文释义
                        </h6>
                        <p class="card-text text-success">${item['definition-ch']}</p>
                        ` : ''}
                    </div>
                    
                    ${usageText ? `
                    <div class="mb-3">
                        <h6 class="text-info mb-1">
                            <i class="bi bi-lightning"></i> 常见用法
                        </h6>
                        <div class="usage-tags">
                            ${usageText.split(' • ').map(usage => 
                                `<span class="badge bg-info me-1 mb-1">${usage}</span>`
                            ).join('')}
                        </div>
                    </div>
                    ` : ''}
                    
                    <div class="card-footer bg-transparent border-0 px-0 pb-0">
                        <small class="text-muted">
                            <i class="bi bi-clock"></i> 提取时间: ${new Date().toLocaleTimeString()}
                        </small>
                    </div>
                </div>
            </div>
        </div>`;
        container.append(card);
    });
}

// 显示加载动画
function showLoading() {
    console.log('显示加载动画');
    $('#loadingSpinner').addClass('show').show();
}

// 隐藏加载动画
function hideLoading() {
    console.log('隐藏加载动画');
    $('#loadingSpinner').removeClass('show').hide();
}

// 显示错误消息
function showError(message) {
    alert('错误: ' + message);
}

// 显示成功消息
function showSuccess(message) {
    // 可以在这里添加更优雅的成功提示
    console.log('成功: ' + message);
}

// 处理词汇提取
function handleExtractVocabulary(article, difficulty) {
    showLoading();
    
    $.ajax({
        url: '/extract',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            article: article,
            difficulty: difficulty
        }),
        success: function(response) {
            console.log('请求成功，响应:', response);
            hideLoading();
            
            if (response.error) {
                showError(response.error);
                return;
            }
            
            // 保存结果
            currentVocabulary = response.vocabulary || [];
            
            // 更新结果计数
            const wordCount = currentVocabulary.filter(item => item.type === 'word').length;
            const phraseCount = currentVocabulary.filter(item => item.type === 'phrase').length;
            let countText = '';
            if (wordCount > 0 && phraseCount > 0) {
                countText = `${wordCount} 个单词 + ${phraseCount} 个词组`;
            } else if (wordCount > 0) {
                countText = `${wordCount} 个单词`;
            } else if (phraseCount > 0) {
                countText = `${phraseCount} 个词组`;
            }
            $('#resultCount').text(countText);
            
            // 渲染词汇列表
            renderVocabularyList(currentVocabulary);
            
            // 显示结果卡片
            $('#resultCard').show();
            
            showSuccess('词汇提取完成');
        },
        error: function(xhr, status, error) {
            console.log('请求失败:', status, error);
            hideLoading();
            let errorMsg = '请求失败，请重试';
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = xhr.responseJSON.error;
            }
            showError(errorMsg);
        }
    });
}

// 处理Excel导出
function handleExportExcel() {
    if (currentVocabulary.length === 0) {
        showError('没有可导出的词汇');
        return;
    }
    
    const exportBtn = $('#exportBtn');
    const originalText = exportBtn.html();
    exportBtn.html('<span class="spinner-border spinner-border-sm" role="status"></span> 导出中...');
    exportBtn.prop('disabled', true);
    
    $.ajax({
        url: '/export',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            vocabulary: currentVocabulary
        }),
        success: function(response) {
            exportBtn.html(originalText);
            exportBtn.prop('disabled', false);
            
            if (response.error) {
                showError('导出失败: ' + response.error);
                return;
            }
            
            if (!response.download_url) {
                showError('导出失败: 未获取到下载链接');
                return;
            }
            
            // 触发下载
            try {
                const link = document.createElement('a');
                link.href = response.download_url;
                link.download = '';
                link.style.display = 'none';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                // 显示成功消息
                showSuccessMessage('Excel文件导出成功！');
            } catch (error) {
                showError('下载失败: ' + error.message);
            }
        },
        error: function(xhr) {
            exportBtn.html(originalText);
            exportBtn.prop('disabled', false);
            
            let errorMsg = '导出失败，请重试';
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = xhr.responseJSON.error;
            } else if (xhr.status === 404) {
                errorMsg = '导出服务不可用';
            } else if (xhr.status === 500) {
                errorMsg = '服务器内部错误';
            }
            showError(errorMsg);
        }
    });
}

// 显示成功消息（更优雅的方式）
function showSuccessMessage(message) {
    // 创建临时成功提示
    const successAlert = $(`
        <div class="alert alert-success alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
            <i class="bi bi-check-circle"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    
    $('body').append(successAlert);
    
    // 3秒后自动消失
    setTimeout(() => {
        successAlert.alert('close');
    }, 3000);
}

// 表单验证
function validateForm() {
    const article = $('#articleInput').val().trim();
    const difficulty = $('input[name="difficulty"]:checked').val();
    
    if (!article) {
        showError('请输入英文文章内容');
        return false;
    }
    
    if (!difficulty) {
        showError('请选择词汇难度');
        return false;
    }
    
    return { article, difficulty };
}

// 初始化应用
function initApp() {
    // 确保加载状态初始化为隐藏
    $('#loadingSpinner').removeClass('show').hide();
    
    // 处理表单提交
    $('#extractForm').on('submit', function(e) {
        e.preventDefault();
        
        const formData = validateForm();
        if (!formData) return;
        
        handleExtractVocabulary(formData.article, formData.difficulty);
    });
    
    // 导出Excel
    $('#exportBtn').on('click', function() {
        handleExportExcel();
    });
    
    // 实时表单验证
    $('#articleInput').on('input', function() {
        const isValid = $(this).val().trim().length > 0;
        $(this).toggleClass('is-valid', isValid);
        $(this).toggleClass('is-invalid', !isValid);
    });
    
    // 难度选择变化
    $('input[name="difficulty"]').on('change', function() {
        $('.form-check-input').removeClass('is-valid');
        $(this).addClass('is-valid');
    });
}

// 文档加载完成后初始化
$(document).ready(function() {
    initApp();
}); 