// 全局变量
let currentUser = null;
let currentDirectory = null;
let currentImages = [];
let currentPage = 1;
let totalPages = 1;
let currentImageIndex = 0;
let currentZoom = 1;

// DOM元素
const loginModal = document.getElementById('loginModal');
const mainApp = document.getElementById('mainApp');
const imageViewer = document.getElementById('imageViewer');
const loginForm = document.getElementById('loginForm');
const loginError = document.getElementById('loginError');
const directorySelect = document.getElementById('directorySelect');
const imageGrid = document.getElementById('imageGrid');
const loadingSpinner = document.getElementById('loadingSpinner');
const userInfo = document.getElementById('userInfo');
const logoutBtn = document.getElementById('logoutBtn');

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    bindEvents();
});

function initializeApp() {
    // 检查是否已登录
    checkLoginStatus();
}

function bindEvents() {
    // 登录表单
    loginForm.addEventListener('submit', handleLogin);
    
    // 登出按钮
    logoutBtn.addEventListener('click', handleLogout);
    
    // 目录选择
    directorySelect.addEventListener('change', handleDirectoryChange);
    
    // 排序控件
    document.getElementById('sortBy').addEventListener('change', loadImages);
    document.getElementById('sortOrder').addEventListener('change', loadImages);
    
    // 视图控件
    document.getElementById('gridViewBtn').addEventListener('click', () => setViewMode('grid'));
    document.getElementById('listViewBtn').addEventListener('click', () => setViewMode('list'));
    
    // 缩略图大小
    document.getElementById('thumbnailSize').addEventListener('input', handleThumbnailSizeChange);
    
    // 分页
    document.getElementById('prevPage').addEventListener('click', () => changePage(-1));
    document.getElementById('nextPage').addEventListener('click', () => changePage(1));
    
    // 图片查看器
    document.getElementById('closeViewer').addEventListener('click', closeImageViewer);
    document.getElementById('prevImage').addEventListener('click', () => navigateImage(-1));
    document.getElementById('nextImage').addEventListener('click', () => navigateImage(1));
    
    // 缩放控件
    document.getElementById('zoomIn').addEventListener('click', () => zoomImage(1.2));
    document.getElementById('zoomOut').addEventListener('click', () => zoomImage(0.8));
    document.getElementById('resetZoom').addEventListener('click', resetZoom);
    
    // 星级评分
    const stars = document.querySelectorAll('#starRating i');
    stars.forEach(star => {
        star.addEventListener('click', handleStarRating);
        star.addEventListener('mouseover', handleStarHover);
    });
    
    document.getElementById('starRating').addEventListener('mouseleave', resetStarHover);
    
    // 下载原图
    document.getElementById('downloadOriginal').addEventListener('click', downloadOriginalImage);
    
    // 键盘事件
    document.addEventListener('keydown', handleKeyboard);
    
    // 图片查看器点击事件
    document.getElementById('viewerImage').addEventListener('click', handleImageClick);
}

async function handleLogin(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentUser = data.user;
            showMainApp();
            loadDirectories();
        } else {
            showError(data.error || '登录失败');
        }
    } catch (error) {
        showError('网络错误，请稍后重试');
    }
}

async function handleLogout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        currentUser = null;
        currentDirectory = null;
        currentImages = [];
        showLoginModal();
    } catch (error) {
        console.error('登出失败:', error);
    }
}

function showMainApp() {
    loginModal.classList.add('hidden');
    mainApp.classList.remove('hidden');
    userInfo.textContent = `欢迎, ${currentUser.username}`;
}

function showLoginModal() {
    mainApp.classList.add('hidden');
    imageViewer.classList.add('hidden');
    loginModal.classList.remove('hidden');
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
    loginError.style.display = 'none';
}

function showError(message) {
    loginError.textContent = message;
    loginError.style.display = 'block';
}

async function loadDirectories() {
    try {
        const response = await fetch('/api/directories');
        const directories = await response.json();
        
        directorySelect.innerHTML = '<option value="">选择目录...</option>';
        directories.forEach(dir => {
            const option = document.createElement('option');
            option.value = dir.path;
            option.textContent = dir.name;
            directorySelect.appendChild(option);
        });
    } catch (error) {
        console.error('加载目录失败:', error);
    }
}

async function handleDirectoryChange() {
    currentDirectory = directorySelect.value;
    if (currentDirectory) {
        currentPage = 1;
        await loadImages();
    } else {
        imageGrid.innerHTML = '';
    }
}

async function loadImages() {
    if (!currentDirectory) return;
    
    showLoading(true);
    
    const sortBy = document.getElementById('sortBy').value;
    const sortOrder = document.getElementById('sortOrder').value;
    
    try {
        const response = await fetch(`/api/images?directory=${encodeURIComponent(currentDirectory)}&page=${currentPage}&sort_by=${sortBy}&sort_order=${sortOrder}`);
        const data = await response.json();
        
        currentImages = data.images;
        totalPages = data.total_pages;
        
        displayImages(data.images);
        updatePagination();
        
    } catch (error) {
        console.error('加载图片失败:', error);
        imageGrid.innerHTML = '<div class="error">加载图片失败</div>';
    } finally {
        showLoading(false);
    }
}

function displayImages(images) {
    imageGrid.innerHTML = '';
    
    images.forEach((image, index) => {
        const imageItem = createImageItem(image, index);
        imageGrid.appendChild(imageItem);
    });
}

function createImageItem(image, index) {
    const item = document.createElement('div');
    item.className = 'image-item';
    item.addEventListener('click', () => openImageViewer(index));
    
    item.innerHTML = `
        <img class="image-thumbnail" src="/api/image/thumbnail?file_path=${encodeURIComponent(image.file_path)}" alt="${image.metadata.filename}" loading="lazy">
        <div class="image-info">
            <div class="image-name">${image.metadata.filename}</div>
            <div class="image-meta">
                <span class="image-size">${formatFileSize(image.metadata.file_size)}</span>
                <span class="image-rating">${'★'.repeat(image.metadata.rating)}${'☆'.repeat(5 - image.metadata.rating)}</span>
            </div>
        </div>
    `;
    
    return item;
}

function openImageViewer(index) {
    currentImageIndex = index;
    const image = currentImages[index];
    
    imageViewer.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    
    loadImageInViewer(image);
    updateViewerNavigation();
}

async function loadImageInViewer(image) {
    const viewerImage = document.getElementById('viewerImage');
    const viewerImageName = document.getElementById('viewerImageName');
    const viewerImageIndex = document.getElementById('viewerImageIndex');
    
    viewerImageName.textContent = image.metadata.filename;
    viewerImageIndex.textContent = `${currentImageIndex + 1} / ${currentImages.length}`;
    
    viewerImage.src = `/api/image/preview?file_path=${encodeURIComponent(image.file_path)}`;
    
    // 加载元数据
    await loadImageMetadata(image.file_path);
    
    // 重置缩放
    resetZoom();
}

async function loadImageMetadata(filePath) {
    try {
        const response = await fetch(`/api/image/metadata?file_path=${encodeURIComponent(filePath)}`);
        const metadata = await response.json();
        
        displayMetadata(metadata);
        updateStarRating(metadata.rating);
        
    } catch (error) {
        console.error('加载元数据失败:', error);
    }
}

function displayMetadata(metadata) {
    const metadataContent = document.getElementById('imageMetadata');
    
    const basicInfo = [
        { label: '文件名', value: metadata.filename },
        { label: '文件大小', value: formatFileSize(metadata.file_size) },
        { label: '修改时间', value: new Date(metadata.modified_time * 1000).toLocaleString() }
    ];
    
    let html = '';
    
    // 基本信息
    basicInfo.forEach(item => {
        html += `
            <div class="metadata-item">
                <span class="metadata-label">${item.label}</span>
                <span class="metadata-value">${item.value}</span>
            </div>
        `;
    });
    
    // EXIF信息
    if (metadata.exif && Object.keys(metadata.exif).length > 0) {
        html += '<h4 style="margin: 20px 0 10px 0;">EXIF信息</h4>';
        
        const importantExifTags = {
            'Make': '相机品牌',
            'Model': '相机型号',
            'LensModel': '镜头型号',
            'DateTime': '拍摄时间',
            'ExposureTime': '快门速度',
            'FNumber': '光圈',
            'ISOSpeedRatings': 'ISO',
            'FocalLength': '焦距',
            'Flash': '闪光灯'
        };
        
        Object.entries(importantExifTags).forEach(([tag, label]) => {
            if (metadata.exif[tag]) {
                html += `
                    <div class="metadata-item">
                        <span class="metadata-label">${label}</span>
                        <span class="metadata-value">${metadata.exif[tag]}</span>
                    </div>
                `;
            }
        });
    }
    
    metadataContent.innerHTML = html;
}

function updateStarRating(rating) {
    const stars = document.querySelectorAll('#starRating i');
    stars.forEach((star, index) => {
        if (index < rating) {
            star.classList.add('active');
        } else {
            star.classList.remove('active');
        }
    });
}

function handleStarRating(e) {
    const rating = parseInt(e.target.dataset.rating);
    const image = currentImages[currentImageIndex];
    
    setImageRating(image.file_path, rating);
}

function handleStarHover(e) {
    const rating = parseInt(e.target.dataset.rating);
    const stars = document.querySelectorAll('#starRating i');
    
    stars.forEach((star, index) => {
        if (index < rating) {
            star.style.color = '#ffc107';
        } else {
            star.style.color = '#ddd';
        }
    });
}

function resetStarHover() {
    const stars = document.querySelectorAll('#starRating i');
    stars.forEach(star => {
        star.style.color = star.classList.contains('active') ? '#ffc107' : '#ddd';
    });
}

async function setImageRating(filePath, rating) {
    try {
        const response = await fetch('/api/image/rating', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_path: filePath,
                rating: rating
            })
        });
        
        if (response.ok) {
            updateStarRating(rating);
            // 更新当前图片的评分
            currentImages[currentImageIndex].metadata.rating = rating;
        }
    } catch (error) {
        console.error('设置星级失败:', error);
    }
}

function closeImageViewer() {
    imageViewer.classList.add('hidden');
    document.body.style.overflow = 'auto';
}

function navigateImage(direction) {
    const newIndex = currentImageIndex + direction;
    
    if (newIndex >= 0 && newIndex < currentImages.length) {
        currentImageIndex = newIndex;
        loadImageInViewer(currentImages[currentImageIndex]);
        updateViewerNavigation();
    }
}

function updateViewerNavigation() {
    const prevBtn = document.getElementById('prevImage');
    const nextBtn = document.getElementById('nextImage');
    
    prevBtn.style.display = currentImageIndex > 0 ? 'block' : 'none';
    nextBtn.style.display = currentImageIndex < currentImages.length - 1 ? 'block' : 'none';
}

function zoomImage(factor) {
    currentZoom *= factor;
    currentZoom = Math.max(0.1, Math.min(5, currentZoom));
    
    const viewerImage = document.getElementById('viewerImage');
    viewerImage.style.transform = `scale(${currentZoom})`;
    
    document.getElementById('zoomLevel').textContent = `${Math.round(currentZoom * 100)}%`;
}

function resetZoom() {
    currentZoom = 1;
    const viewerImage = document.getElementById('viewerImage');
    viewerImage.style.transform = 'scale(1)';
    document.getElementById('zoomLevel').textContent = '100%';
}

function handleImageClick(e) {
    const rect = e.target.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const clickX = e.clientX;
    
    // 点击中心区域放大/缩小
    if (Math.abs(clickX - centerX) < rect.width * 0.2) {
        if (currentZoom === 1) {
            zoomImage(2);
        } else {
            resetZoom();
        }
    }
    // 点击左侧切换到上一张
    else if (clickX < centerX) {
        navigateImage(-1);
    }
    // 点击右侧切换到下一张
    else {
        navigateImage(1);
    }
}

function downloadOriginalImage() {
    const image = currentImages[currentImageIndex];
    const link = document.createElement('a');
    link.href = `/api/image/download?file_path=${encodeURIComponent(image.file_path)}`;
    link.download = image.metadata.filename;
    link.click();
}

function handleKeyboard(e) {
    if (imageViewer.classList.contains('hidden')) return;
    
    switch (e.key) {
        case 'Escape':
            closeImageViewer();
            break;
        case 'ArrowLeft':
            navigateImage(-1);
            break;
        case 'ArrowRight':
            navigateImage(1);
            break;
        case '+':
        case '=':
            zoomImage(1.2);
            break;
        case '-':
            zoomImage(0.8);
            break;
        case '0':
            resetZoom();
            break;
    }
}

function changePage(direction) {
    const newPage = currentPage + direction;
    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        loadImages();
    }
}

function updatePagination() {
    const pageInfo = document.getElementById('pageInfo');
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    
    pageInfo.textContent = `第 ${currentPage} 页，共 ${totalPages} 页`;
    prevBtn.disabled = currentPage === 1;
    nextBtn.disabled = currentPage === totalPages;
}

function setViewMode(mode) {
    const gridBtn = document.getElementById('gridViewBtn');
    const listBtn = document.getElementById('listViewBtn');
    
    if (mode === 'grid') {
        gridBtn.classList.add('active');
        listBtn.classList.remove('active');
        imageGrid.className = 'image-grid';
    } else {
        listBtn.classList.add('active');
        gridBtn.classList.remove('active');
        imageGrid.className = 'image-grid list-view';
    }
}

function handleThumbnailSizeChange(e) {
    const size = e.target.value;
    const items = document.querySelectorAll('.image-item');
    
    items.forEach(item => {
        item.style.width = `${size}px`;
    });
}

function showLoading(show) {
    if (show) {
        loadingSpinner.style.display = 'flex';
    } else {
        loadingSpinner.style.display = 'none';
    }
}

function formatFileSize(bytes) {
    const sizes = ['B', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

function getFileHash(filePath) {
    // 简单的哈希函数，实际应该与后端保持一致
    // 使用文件路径生成一个简单的哈希
    let hash = 0;
    for (let i = 0; i < filePath.length; i++) {
        const char = filePath.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // 转换为32位整数
    }
    return Math.abs(hash).toString(16);
}

async function checkLoginStatus() {
    try {
        const response = await fetch('/api/directories');
        if (response.ok) {
            // 已登录，显示主界面
            showMainApp();
            loadDirectories();
        } else {
            // 未登录，显示登录界面
            showLoginModal();
        }
    } catch (error) {
        showLoginModal();
    }
}
