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

const ZOOM_LEVELS = [50, 75, 100, 150, 200, 300, 400];
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

  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const currentImage = images.find((img) => img.image_type === activeImage);

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
    if (containerRef.current && imageRef.current) {
      const containerWidth = containerRef.current.clientWidth;
      const containerHeight = containerRef.current.clientHeight;
      const imageWidth = imageRef.current.naturalWidth;
      const imageHeight = imageRef.current.naturalHeight;

      const scaleX = (containerWidth / imageWidth) * 100;
      const scaleY = (containerHeight / imageHeight) * 100;
      const fitZoom = Math.min(scaleX, scaleY, 100);

      const roundedZoom = ZOOM_LEVELS.reduce((prev, curr) =>
        Math.abs(curr - fitZoom) < Math.abs(prev - fitZoom) ? curr : prev
      );

      setZoom(roundedZoom);
      setPosition({ x: 0, y: 0 });
      onZoom?.(roundedZoom);
    }
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

  const imageStyle = {
    transform: `translate(${position.x}px, ${position.y}px) scale(${zoom / 100})`,
    transformOrigin: 'center center',
    filter: `brightness(${brightness}%) contrast(${contrast}%) ${invert ? 'invert(1)' : ''}`,
  };

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
        className="flex-1 overflow-hidden relative cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {currentImage?.image_url ? (
          <>
            <img
              ref={imageRef}
              src={resolveImageUrl(currentImage.image_url)}
              alt={`Check ${activeImage}`}
              style={imageStyle}
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 max-w-none"
              draggable={false}
            />

            {/* ROI overlays */}
            {showROI && roiRegions.map((roi) => (
              <div
                key={roi.id}
                className="absolute border-2 pointer-events-none"
                style={{
                  left: `calc(50% + ${position.x}px + ${(roi.x - 50) * zoom / 100}%)`,
                  top: `calc(50% + ${position.y}px + ${(roi.y - 50) * zoom / 100}%)`,
                  width: `${roi.width * zoom / 100}%`,
                  height: `${roi.height * zoom / 100}%`,
                  borderColor: roi.color,
                  transform: 'translate(-50%, -50%)',
                }}
              >
                <span
                  className="absolute -top-5 left-0 text-xs px-1 rounded"
                  style={{ backgroundColor: roi.color, color: 'white' }}
                >
                  {roi.name}
                </span>
              </div>
            ))}

            {/* Magnifier */}
            {showMagnifier && (
              <div
                className="magnifier"
                style={{
                  left: magnifierPos.x - 75,
                  top: magnifierPos.y - 75,
                  backgroundImage: `url(${resolveImageUrl(currentImage.image_url)})`,
                  backgroundPosition: `${-magnifierPos.x * 2 + 75}px ${-magnifierPos.y * 2 + 75}px`,
                  backgroundSize: `${zoom * 4}%`,
                  filter: imageStyle.filter,
                }}
              />
            )}
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
