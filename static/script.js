// 全局变量
let currentUser = null;
let currentDirectory = null;
let currentImages = [];
let currentSubdirectories = [];
let availableDirectories = [];
let currentPage = 1;
let totalPages = 1;
let currentImageIndex = 0;
let currentZoom = 1;

// Pinterest瀑布流布局变量
let columnHeights = [];
let columnCount = 0;
let itemWidth = 236;
let itemGap = 16;
let columns = [];

// 工具函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

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
    
    // 窗口大小变化时重新布局
    window.addEventListener('resize', debounce(() => {
        if (imageGrid && imageGrid.children.length > 0) {
            layoutWaterfall();
        }
    }, 300));
    
    // 缩略图大小
    document.getElementById('thumbnailSize').addEventListener('input', handleThumbnailSizeChange);
    
    // 分页
    document.getElementById('prevPage').addEventListener('click', () => changePage(-1));
    document.getElementById('nextPage').addEventListener('click', () => changePage(1));
    
    // 图片查看器
    document.getElementById('closeViewer').addEventListener('click', closeImageViewer);
    document.getElementById('prevImage').addEventListener('click', (e) => {
        e.stopPropagation();
        navigateImage(-1);
    });
    document.getElementById('nextImage').addEventListener('click', (e) => {
        e.stopPropagation();
        navigateImage(1);
    });
    
    // 缩放控件
    document.getElementById('zoomIn').addEventListener('click', (e) => {
        e.stopPropagation();
        zoomImage(1.2);
    });
    document.getElementById('zoomOut').addEventListener('click', (e) => {
        e.stopPropagation();
        zoomImage(0.8);
    });
    document.getElementById('resetZoom').addEventListener('click', (e) => {
        e.stopPropagation();
        resetZoom();
    });
    
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
    
    // 点击viewer-main任意位置关闭页面
    document.querySelector('.viewer-main').addEventListener('click', closeImageViewer);
    
    // 阻止图片容器内的点击事件冒泡
    document.querySelector('.image-container').addEventListener('click', (e) => {
        e.stopPropagation();
    });
    
    // 添加图片拖动功能
    addImageDragFunctionality();
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
        
        // 存储可用目录到全局变量
        availableDirectories = directories;
        
        directorySelect.innerHTML = '<option value="">选择目录...</option>';
        directories.forEach(dir => {
            const option = document.createElement('option');
            option.value = dir.path;
            option.textContent = dir.name;
            directorySelect.appendChild(option);
        });
        
        // 自动选择第一个目录
        if (directories.length > 0) {
            directorySelect.value = directories[0].path;
            currentDirectory = directories[0].path;
            currentPage = 1;
            await loadImages();
        }
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
        const response = await fetch(`/api/browse?directory=${encodeURIComponent(currentDirectory)}&page=${currentPage}&sort_by=${sortBy}&sort_order=${sortOrder}`);
        const data = await response.json();
        
        currentImages = data.images;
        currentSubdirectories = data.subdirectories || [];
        totalPages = data.total_pages;
        
        displayContent(data.subdirectories || [], data.images);
        updatePagination();
        updateBreadcrumb();
        
    } catch (error) {
        console.error('加载内容失败:', error);
        imageGrid.innerHTML = '<div class="error">加载内容失败</div>';
    } finally {
        showLoading(false);
    }
}

function displayContent(subdirectories, images) {
    imageGrid.innerHTML = '';
    
    // 显示子文件夹 - 过滤掉完全空的文件夹
    if (subdirectories && Array.isArray(subdirectories)) {
        // 显示当前目录有图片的文件夹，或者有预览图片（来自子目录）的文件夹
        const nonEmptyDirectories = subdirectories.filter(subdir => subdir.image_count > 0 || subdir.preview_image);
        nonEmptyDirectories.forEach(subdir => {
            const folderItem = createFolderItem(subdir);
            imageGrid.appendChild(folderItem);
        });
    }
    
    // 显示图片
    if (images && Array.isArray(images)) {
        images.forEach((image, index) => {
            const imageItem = createImageItem(image, index);
            imageGrid.appendChild(imageItem);
        });
    }
    
    // 应用瀑布流布局
    setTimeout(() => {
        layoutWaterfall();
    }, 100);
}

function displayImages(images) {
    imageGrid.innerHTML = '';
    
    images.forEach((image, index) => {
        const imageItem = createImageItem(image, index);
        imageGrid.appendChild(imageItem);
    });
}

function createFolderItem(subdir) {
    const folderItem = document.createElement('div');
    folderItem.className = 'folder-item';
    folderItem.onclick = () => navigateToSubdirectory(subdir.path);

    // 创建预览图片容器
    const previewContainer = document.createElement('div');
    previewContainer.className = 'folder-preview';

    if (subdir.preview_image) {
        // 如果有预览图片，显示图片
        const previewImg = document.createElement('img');
        previewImg.className = 'folder-preview-image';
        previewImg.src = `/api/image/thumbnail?file_path=${encodeURIComponent(subdir.preview_image.file_path)}`;
        previewImg.alt = subdir.name;
        previewImg.loading = 'lazy';
        previewContainer.appendChild(previewImg);
    } else {
        // 如果没有预览图片，显示默认背景
        previewContainer.className += ' folder-preview-empty';
        previewContainer.innerHTML = '<div class="folder-empty-text">空文件夹</div>';
    }

    // 创建文件夹图标（放在角落）
    const folderIcon = document.createElement('div');
    folderIcon.className = 'folder-corner-icon';
    folderIcon.innerHTML = '📁';
    previewContainer.appendChild(folderIcon);

    // 创建文件夹名称和图片数量，直接放在previewContainer上
    const folderName = document.createElement('div');
    folderName.className = 'folder-name';
    folderName.textContent = subdir.name;

    const folderCount = document.createElement('div');
    folderCount.className = 'folder-info';
    folderCount.textContent = `${subdir.image_count || 0} 张图片`;

    folderItem.appendChild(previewContainer);
    folderItem.appendChild(folderName);
    folderItem.appendChild(folderCount);

    return folderItem;
}

function createImageItem(image, index) {
    const imageItem = document.createElement('div');
    imageItem.className = 'image-item';
    imageItem.onclick = () => openImageViewer(index);
    
    const img = document.createElement('img');
    img.className = 'image-thumbnail';
    img.src = `/api/image/thumbnail?file_path=${encodeURIComponent(image.file_path)}`;
    img.alt = image.metadata.filename;
    img.loading = 'lazy';
    
    // 直接添加图片到imageItem，不添加额外的白色方块和星星评分
    imageItem.appendChild(img);
    
    return imageItem;
}

// Pinterest瀑布流布局函数
function initWaterfallLayout() {
    const container = imageGrid;
    if (!container) return;
    
    const containerWidth = window.innerWidth > 1400 ? 1400 : window.innerWidth; // 限制最大宽度
    
    // 重置容器
    container.style.height = 'auto';
    container.style.position = 'relative';
    
    // 根据屏幕宽度调整项目宽度 - 更智能的Pinterest风格
    if (window.innerWidth <= 480) {
        // 移动端单列
        columnCount = 1;
        itemWidth = containerWidth - 40; // 减去左右padding
        itemGap = 12;
    } else if (window.innerWidth <= 768) {
        // 平板两列
        columnCount = 2;
        itemWidth = (containerWidth - 60 - itemGap) / columnCount; // 减去左右padding和间距
        itemGap = 12;
    } else if (window.innerWidth <= 1024) {
        // 小屏幕三列
        columnCount = 3;
        itemWidth = (containerWidth - 60 - (columnCount - 1) * itemGap) / columnCount;
        itemGap = 14;
    } else if (window.innerWidth <= 1200) {
        // 中等屏幕四列
        columnCount = 4;
        itemWidth = (containerWidth - 60 - (columnCount - 1) * itemGap) / columnCount;
        itemGap = 16;
    } else {
        // 大屏幕五列
        columnCount = 5;
        itemWidth = (containerWidth - 60 - (columnCount - 1) * itemGap) / columnCount;
        itemGap = 16;
    }
    
    // 确保项目宽度为整数，避免布局问题
    itemWidth = Math.floor(itemWidth);
    
    // 初始化列高度数组
    columnHeights = new Array(columnCount).fill(0);
}

function layoutWaterfallItem(element, index) {
    return new Promise((resolve) => {
        const img = element.querySelector('.image-thumbnail');
        
        // 如果没有找到图片元素，直接使用默认高度
        if (!img) {
            positionItem(element, null);
            resolve();
            return;
        }
        
        // 检查图片是否已经加载完成
        if (img.complete) {
            positionItem(element, img);
            resolve();
        } else {
            // 如果图片尚未加载完成，设置加载完成后的回调
            const onLoad = () => {
                img.removeEventListener('load', onLoad);
                img.removeEventListener('error', onError);
                positionItem(element, img);
                resolve();
            };
            
            const onError = () => {
                img.removeEventListener('load', onLoad);
                img.removeEventListener('error', onError);
                positionItem(element, null);
                resolve();
            };
            
            img.addEventListener('load', onLoad);
            img.addEventListener('error', onError);
        }
    });
}

function positionItem(element, img) {
    // 找到最短的列
    let shortestColumn = 0;
    let minHeight = columnHeights[0];
    
    for (let i = 1; i < columnCount; i++) {
        if (columnHeights[i] < minHeight) {
            minHeight = columnHeights[i];
            shortestColumn = i;
        }
    }
    
    // 计算位置
    const left = shortestColumn * (itemWidth + itemGap);
    const top = columnHeights[shortestColumn];
    
    // 设置元素位置
    element.style.left = left + 'px';
    element.style.top = top + 'px';
    element.style.width = itemWidth + 'px';
    
    // 计算元素高度
    let itemHeight = itemWidth; // 默认高度
    
    if (img && img.naturalWidth && img.naturalHeight) {
        // 根据图片比例计算高度
        const aspectRatio = img.naturalHeight / img.naturalWidth;
        const imageHeight = itemWidth * aspectRatio;
        const infoHeight = element.querySelector('.image-info') ? 50 : 0;
        itemHeight = imageHeight + infoHeight;
    } else if (element.classList.contains('folder-item')) {
        // 计算文件夹项目的实际高度
        const previewHeight = 220; // 增加预览区域高度，显示更多图片内容
        const infoHeight = 60; // 减少信息区域高度，减少空白
        itemHeight = previewHeight + infoHeight;
    } else {
        // 其他项目的默认高度
        itemHeight = itemWidth + 50;
    }
    
    // 更新列高度
    columnHeights[shortestColumn] += itemHeight + itemGap;
    
    // 更新容器高度
    const maxHeight = Math.max(...columnHeights);
    imageGrid.style.height = maxHeight + 'px';
}

async function layoutWaterfall() {
    if (!imageGrid) return;
    
    initWaterfallLayout();
    
    const items = imageGrid.querySelectorAll('.image-item, .folder-item');
    
    // 并行布局元素以提高性能
    const promises = Array.from(items).map((item, index) => layoutWaterfallItem(item, index));
    await Promise.all(promises);
}

// 导航到子目录
function navigateToSubdirectory(path) {
    currentDirectory = path;
    currentPage = 1;
    loadImages();
}

// 更新面包屑导航
function updateBreadcrumb() {
    const breadcrumbContainer = document.querySelector('.breadcrumb');
    if (!breadcrumbContainer) {
        // 如果没有面包屑容器，创建一个
        const toolbar = document.querySelector('.toolbar');
        const breadcrumb = document.createElement('div');
        breadcrumb.className = 'breadcrumb';
        toolbar.insertBefore(breadcrumb, toolbar.firstChild);
    }
    
    const breadcrumb = document.querySelector('.breadcrumb');
    breadcrumb.innerHTML = '';
    
    if (!currentDirectory) return;
    
    // 获取配置的根目录
    let rootDir = '';
    let displayPath = currentDirectory;
    
    // 找到当前目录属于哪个根目录
    for (const dir of availableDirectories) {
        if (currentDirectory.startsWith(dir.path)) {
            rootDir = dir.path;
            displayPath = currentDirectory.substring(dir.path.length);
            if (displayPath.startsWith('\\') || displayPath.startsWith('/')) {
                displayPath = displayPath.substring(1);
            }
            break;
        }
    }
    
    // 添加根目录
    const rootItem = document.createElement('span');
    rootItem.className = 'breadcrumb-item clickable';
    rootItem.textContent = '根目录';
    rootItem.onclick = () => navigateToSubdirectory(rootDir);
    breadcrumb.appendChild(rootItem);
    
    if (displayPath) {
        const parts = displayPath.split(/[\\\/]/);
        let currentPath = rootDir;
        
        parts.forEach((part, index) => {
            if (part) {
                currentPath += (currentPath.endsWith('\\') || currentPath.endsWith('/') ? '' : '\\') + part;
                
                const separator = document.createElement('span');
                separator.className = 'breadcrumb-separator';
                separator.textContent = ' > ';
                breadcrumb.appendChild(separator);
                
                const item = document.createElement('span');
                item.className = index === parts.length - 1 ? 'breadcrumb-item current' : 'breadcrumb-item clickable';
                item.textContent = part;
                
                if (index < parts.length - 1) {
                    const pathToNavigate = currentPath;
                    item.onclick = () => navigateToSubdirectory(pathToNavigate);
                }
                
                breadcrumb.appendChild(item);
            }
        });
    }
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
    viewerImage.style.transform = `scale(${currentZoom}) translate(${translateX}px, ${translateY}px)`;
    
    document.getElementById('zoomLevel').textContent = `${Math.round(currentZoom * 100)}%`;
}

// 拖动相关变量
let isDragging = false;
let startX, startY;
let translateX = 0, translateY = 0;
let startTranslateX, startTranslateY;

function resetZoom() {
    currentZoom = 1;
    translateX = 0;
    translateY = 0;
    const viewerImage = document.getElementById('viewerImage');
    viewerImage.style.transform = 'scale(1)';
    document.getElementById('zoomLevel').textContent = '100%';
}

function addImageDragFunctionality() {
    const viewerImage = document.getElementById('viewerImage');
    const imageContainer = document.querySelector('.image-container');
    
    // 鼠标按下事件
    viewerImage.addEventListener('mousedown', startDrag);
    
    // 鼠标移动事件
    imageContainer.addEventListener('mousemove', drag);
    
    // 鼠标释放事件
    document.addEventListener('mouseup', stopDrag);
    
    // 鼠标离开容器事件
    imageContainer.addEventListener('mouseleave', stopDrag);
    
    // 触摸事件 - 支持手机模式
    viewerImage.addEventListener('touchstart', startDrag);
    viewerImage.addEventListener('touchmove', drag);
    document.addEventListener('touchend', stopDrag);
}

function startDrag(e) {
    // 只有在图片被放大后才能拖动
    if (currentZoom <= 1) return;
    
    isDragging = true;
    
    // 处理鼠标事件和触摸事件
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    
    // 记录初始位置
    startX = clientX;
    startY = clientY;
    startTranslateX = translateX;
    startTranslateY = translateY;
    
    // 防止默认行为
    e.preventDefault();
    
    // 改变鼠标样式
    document.body.style.cursor = 'grabbing';
}

function drag(e) {
    if (!isDragging) return;
    
    // 处理鼠标事件和触摸事件
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    
    // 计算移动距离
    const dx = clientX - startX;
    const dy = clientY - startY;
    
    // 更新平移量
    translateX = startTranslateX + dx;
    translateY = startTranslateY + dy;
    
    // 应用变换
    const viewerImage = document.getElementById('viewerImage');
    viewerImage.style.transform = `scale(${currentZoom}) translate(${translateX}px, ${translateY}px)`;
    
    // 触摸事件时阻止默认行为
    if (e.touches) {
        e.preventDefault();
    }
}

function stopDrag() {
    if (!isDragging) return;
    
    isDragging = false;
    
    // 恢复鼠标样式
    document.body.style.cursor = '';
}

function handleImageClick(e) {
    // 如果图片被放大，只允许拖动，不执行其他点击操作
    if (currentZoom > 1) {
        return;
    }
    
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
        const response = await fetch('/api/auth/status');
        if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
                // 已登录，设置用户信息并显示主界面
                currentUser = data.user;
                showMainApp();
                loadDirectories();
            } else {
                showLoginModal();
            }
        } else {
            // 未登录，显示登录界面
            showLoginModal();
        }
    } catch (error) {
        showLoginModal();
    }
}
