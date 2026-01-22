import { useState, useRef, useCallback, useEffect } from 'react';
import {
  MagnifyingGlassPlusIcon,
  MagnifyingGlassMinusIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  AdjustmentsHorizontalIcon,
  EyeIcon,
  SunIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';
import { CheckImage, ROIRegion } from '../../types';
import { imageApi, resolveImageUrl } from '../../services/api';

interface CheckImageViewerProps {
  images: CheckImage[];
  roiRegions?: ROIRegion[];
  showROI?: boolean;
  onZoom?: (level: number) => void;
}

const ZOOM_LEVELS = [50, 75, 100, 125, 150, 200, 300, 400];
const DEFAULT_ZOOM = 100;

export default function CheckImageViewer({
  images,
  roiRegions = [],
  showROI: initialShowROI = true,
  onZoom,
}: CheckImageViewerProps) {
  const [activeImage, setActiveImage] = useState<'front' | 'back'>('front');
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [showMagnifier, setShowMagnifier] = useState(false);
  const [magnifierPos, setMagnifierPos] = useState({ x: 0, y: 0 });
  const [showROI, setShowROI] = useState(initialShowROI);
  const [brightness, setBrightness] = useState(100);
  const [contrast, setContrast] = useState(100);
  const [invert, setInvert] = useState(false);
  const [showControls, setShowControls] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 });
  const [containerDimensions, setContainerDimensions] = useState({ width: 0, height: 0 });

  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const imageWrapperRef = useRef<HTMLDivElement>(null);

  const currentImage = images.find((img) => img.image_type === activeImage);

  // Reset image state when image changes
  useEffect(() => {
    setImageError(null);
    setImageLoaded(false);
    setPosition({ x: 0, y: 0 });
  }, [activeImage, currentImage?.image_url]);

  const handleZoomIn = useCallback(() => {
    const currentIndex = ZOOM_LEVELS.indexOf(zoom);
    if (currentIndex < ZOOM_LEVELS.length - 1) {
      const newZoom = ZOOM_LEVELS[currentIndex + 1];
      setZoom(newZoom);
      onZoom?.(newZoom);
    }
  }, [zoom, onZoom]);

  const handleZoomOut = useCallback(() => {
    const currentIndex = ZOOM_LEVELS.indexOf(zoom);
    if (currentIndex > 0) {
      const newZoom = ZOOM_LEVELS[currentIndex - 1];
      setZoom(newZoom);
      onZoom?.(newZoom);
    }
  }, [zoom, onZoom]);

  const handleZoomPreset = useCallback((level: number) => {
    setZoom(level);
    onZoom?.(level);
    if (level === 100) {
      setPosition({ x: 0, y: 0 });
    }
  }, [onZoom]);

  const handleFitToScreen = useCallback(() => {
    setZoom(100);
    setPosition({ x: 0, y: 0 });
    onZoom?.(100);
  }, [onZoom]);

  // Mouse drag handling
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  }, [position]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging) {
      setPosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }

    // Update magnifier position
    if (showMagnifier && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setMagnifierPos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    }
  }, [isDragging, dragStart, showMagnifier]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        handleZoomIn();
      } else if (e.key === '-') {
        e.preventDefault();
        handleZoomOut();
      } else if (e.key === '0') {
        e.preventDefault();
        handleZoomPreset(100);
      } else if (e.key === 'f') {
        e.preventDefault();
        handleFitToScreen();
      } else if (e.key === 'm') {
        e.preventDefault();
        setShowMagnifier(!showMagnifier);
      } else if (e.key === 'r') {
        e.preventDefault();
        setShowROI(!showROI);
      } else if (e.key === 'Tab') {
        e.preventDefault();
        setActiveImage(activeImage === 'front' ? 'back' : 'front');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleZoomIn, handleZoomOut, handleZoomPreset, handleFitToScreen, showMagnifier, showROI, activeImage]);

  // Log zoom usage
  useEffect(() => {
    if (zoom !== DEFAULT_ZOOM && currentImage) {
      imageApi.logZoom(currentImage.id, zoom).catch(() => {});
    }
  }, [zoom, currentImage]);

  // Track container dimensions for magnifier calculations
  useEffect(() => {
    const updateContainerDimensions = () => {
      if (containerRef.current) {
        setContainerDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    updateContainerDimensions();
    window.addEventListener('resize', updateContainerDimensions);
    return () => window.removeEventListener('resize', updateContainerDimensions);
  }, []);

  const handleImageLoad = useCallback(() => {
    setImageLoaded(true);
    if (imageRef.current) {
      setImageDimensions({
        width: imageRef.current.naturalWidth,
        height: imageRef.current.naturalHeight,
      });
    }
    // Update container dimensions when image loads
    if (containerRef.current) {
      setContainerDimensions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });
    }
  }, []);

  const imageFilters = `brightness(${brightness}%) contrast(${contrast}%) ${invert ? 'invert(1)' : ''}`;

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        {/* Image selector */}
        <div className="flex space-x-2">
          <button
            onClick={() => setActiveImage('front')}
            className={clsx(
              'px-3 py-1 text-sm font-medium rounded',
              activeImage === 'front'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            )}
          >
            Front
          </button>
          <button
            onClick={() => setActiveImage('back')}
            className={clsx(
              'px-3 py-1 text-sm font-medium rounded',
              activeImage === 'back'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            )}
          >
            Back
          </button>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleZoomOut}
            className="p-1 text-gray-300 hover:text-white rounded hover:bg-gray-700"
            title="Zoom Out (-)"
          >
            <MagnifyingGlassMinusIcon className="h-5 w-5" />
          </button>

          <select
            value={zoom}
            onChange={(e) => handleZoomPreset(Number(e.target.value))}
            className="bg-gray-700 text-white text-sm rounded px-2 py-1 border-none focus:ring-2 focus:ring-primary-500"
          >
            {ZOOM_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}%
              </option>
            ))}
          </select>

          <button
            onClick={handleZoomIn}
            className="p-1 text-gray-300 hover:text-white rounded hover:bg-gray-700"
            title="Zoom In (+)"
          >
            <MagnifyingGlassPlusIcon className="h-5 w-5" />
          </button>

          <div className="w-px h-6 bg-gray-600 mx-2" />

          <button
            onClick={handleFitToScreen}
            className="p-1 text-gray-300 hover:text-white rounded hover:bg-gray-700"
            title="Fit to Screen (F)"
          >
            <ArrowsPointingInIcon className="h-5 w-5" />
          </button>

          <button
            onClick={() => handleZoomPreset(100)}
            className="p-1 text-gray-300 hover:text-white rounded hover:bg-gray-700"
            title="Actual Size (0)"
          >
            <ArrowsPointingOutIcon className="h-5 w-5" />
          </button>

          <div className="w-px h-6 bg-gray-600 mx-2" />

          <button
            onClick={() => setShowMagnifier(!showMagnifier)}
            className={clsx(
              'p-1 rounded',
              showMagnifier
                ? 'bg-primary-600 text-white'
                : 'text-gray-300 hover:text-white hover:bg-gray-700'
            )}
            title="Magnifier (M)"
          >
            <EyeIcon className="h-5 w-5" />
          </button>

          <button
            onClick={() => setShowROI(!showROI)}
            className={clsx(
              'p-1 rounded',
              showROI
                ? 'bg-primary-600 text-white'
                : 'text-gray-300 hover:text-white hover:bg-gray-700'
            )}
            title="Show ROI (R)"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <rect x="3" y="3" width="18" height="18" rx="2" strokeWidth="2" />
              <line x1="3" y1="9" x2="21" y2="9" strokeWidth="2" />
              <line x1="9" y1="3" x2="9" y2="21" strokeWidth="2" />
            </svg>
          </button>

          <button
            onClick={() => setShowControls(!showControls)}
            className={clsx(
              'p-1 rounded',
              showControls
                ? 'bg-primary-600 text-white'
                : 'text-gray-300 hover:text-white hover:bg-gray-700'
            )}
            title="Image Controls"
          >
            <AdjustmentsHorizontalIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Image controls panel */}
      {showControls && (
        <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center space-x-6">
          <div className="flex items-center space-x-2">
            <SunIcon className="h-4 w-4 text-gray-400" />
            <span className="text-xs text-gray-400">Brightness</span>
            <input
              type="range"
              min="50"
              max="150"
              value={brightness}
              onChange={(e) => setBrightness(Number(e.target.value))}
              className="w-24"
            />
            <span className="text-xs text-gray-300 w-8">{brightness}%</span>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-xs text-gray-400">Contrast</span>
            <input
              type="range"
              min="50"
              max="150"
              value={contrast}
              onChange={(e) => setContrast(Number(e.target.value))}
              className="w-24"
            />
            <span className="text-xs text-gray-300 w-8">{contrast}%</span>
          </div>

          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="checkbox"
              checked={invert}
              onChange={(e) => setInvert(e.target.checked)}
              className="rounded border-gray-600"
            />
            <span className="text-xs text-gray-400">Invert</span>
          </label>

          <button
            onClick={() => {
              setBrightness(100);
              setContrast(100);
              setInvert(false);
            }}
            className="text-xs text-primary-400 hover:text-primary-300"
          >
            Reset
          </button>
        </div>
      )}

      {/* Image container */}
      <div
        ref={containerRef}
        className="flex-1 overflow-hidden relative cursor-grab active:cursor-grabbing flex items-center justify-center"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {currentImage?.image_url ? (
          <>
            {/* Loading indicator */}
            {!imageLoaded && !imageError && (
              <div className="absolute inset-0 flex items-center justify-center z-10">
                <div className="text-gray-400">Loading image...</div>
              </div>
            )}

            {/* Error message */}
            {imageError && (
              <div className="absolute inset-0 flex items-center justify-center z-10">
                <div className="text-center text-red-400">
                  <p>Failed to load image</p>
                  <p className="text-xs text-gray-500 mt-1">{imageError}</p>
                </div>
              </div>
            )}

            {/* Image and ROI wrapper - transforms applied here */}
            <div
              ref={imageWrapperRef}
              className="relative"
              style={{
                transform: `translate(${position.x}px, ${position.y}px) scale(${zoom / 100})`,
                transformOrigin: 'center center',
                visibility: imageLoaded && !imageError ? 'visible' : 'hidden',
              }}
            >
              <img
                ref={imageRef}
                src={resolveImageUrl(currentImage.image_url)}
                alt={`Check ${activeImage}`}
                style={{
                  filter: imageFilters,
                  maxWidth: '100%',
                  maxHeight: '100%',
                }}
                className="block"
                draggable={false}
                onLoad={handleImageLoad}
                onError={(e) => {
                  const img = e.target as HTMLImageElement;
                  setImageError(`URL: ${img.src.substring(0, 80)}...`);
                  console.error('Image load failed:', img.src);
                }}
              />

              {/* ROI overlays - positioned relative to the image */}
              {showROI && imageLoaded && roiRegions.map((roi) => (
                <div
                  key={roi.id}
                  className="absolute border-2 pointer-events-none"
                  style={{
                    left: `${roi.x}%`,
                    top: `${roi.y}%`,
                    width: `${roi.width}%`,
                    height: `${roi.height}%`,
                    borderColor: roi.color,
                  }}
                >
                  <span
                    className="absolute -top-5 left-0 text-xs px-1 rounded whitespace-nowrap"
                    style={{ backgroundColor: roi.color, color: 'white' }}
                  >
                    {roi.name}
                  </span>
                </div>
              ))}
            </div>

            {/* Magnifier */}
            {showMagnifier && imageLoaded && (() => {
              // Calculate the displayed image size at current zoom
              const displayedWidth = imageDimensions.width * zoom / 100;
              const displayedHeight = imageDimensions.height * zoom / 100;

              // The image wrapper is centered in the container, then translated by position
              // Image wrapper center before pan: (containerWidth/2, containerHeight/2)
              // Image wrapper center after pan: (containerWidth/2 + position.x, containerHeight/2 + position.y)
              // Image top-left in container coords:
              const imageLeft = (containerDimensions.width - displayedWidth) / 2 + position.x;
              const imageTop = (containerDimensions.height - displayedHeight) / 2 + position.y;

              // Cursor position relative to the displayed image
              const cursorOnImageX = magnifierPos.x - imageLeft;
              const cursorOnImageY = magnifierPos.y - imageTop;

              // Convert to original image coordinates (before zoom)
              const originalImageX = cursorOnImageX / (zoom / 100);
              const originalImageY = cursorOnImageY / (zoom / 100);

              // For the magnifier, we show the image at 2x the current zoom
              const magnifierZoom = 2;
              const bgWidth = imageDimensions.width * magnifierZoom;
              const bgHeight = imageDimensions.height * magnifierZoom;

              // Position the background so that originalImageX/Y appears at center of magnifier (75, 75)
              const bgPosX = 75 - originalImageX * magnifierZoom;
              const bgPosY = 75 - originalImageY * magnifierZoom;

              return (
                <div
                  className="magnifier"
                  style={{
                    position: 'absolute',
                    left: magnifierPos.x - 75,
                    top: magnifierPos.y - 75,
                    width: 150,
                    height: 150,
                    borderRadius: '50%',
                    border: '3px solid white',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                    backgroundImage: `url(${resolveImageUrl(currentImage.image_url)})`,
                    backgroundPosition: `${bgPosX}px ${bgPosY}px`,
                    backgroundSize: `${bgWidth}px ${bgHeight}px`,
                    backgroundRepeat: 'no-repeat',
                    filter: imageFilters,
                    pointerEvents: 'none',
                    zIndex: 20,
                  }}
                />
              );
            })()}
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            No image available
          </div>
        )}
      </div>

      {/* Keyboard shortcuts help */}
      <div className="px-4 py-1 bg-gray-800 text-xs text-gray-500 flex justify-center space-x-4">
        <span>+/- Zoom</span>
        <span>0 Reset</span>
        <span>F Fit</span>
        <span>M Magnifier</span>
        <span>R ROI</span>
        <span>Tab Switch</span>
      </div>
    </div>
  );
}
