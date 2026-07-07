import { ColorSwatch } from '@mantine/core';
import { Button } from '@/components/ui/button';
import { useEffect, useRef, useState, useCallback } from 'react';
import axios from 'axios';
import html2canvas from 'html2canvas';
import Draggable from 'react-draggable';
import {SWATCHES} from '@/constants';
import { Eraser, Pencil, RotateCcw, Play, Palette, CornerUpLeft, CornerUpRight, Download, Share2, Loader2 } from 'lucide-react';
import logo from '/logo.svg';
import { sanitizeLatex, isSafeObjectKey, validateCalculateResponse, validateFileUpload, sanitizeFilename } from '@/lib/sanitize';

interface Response {
    expr: string;
    result: string;
    assign: boolean;
}

const MAX_CANVAS_DATA_URL_SIZE = 10 * 1024 * 1024;

export default function Home() {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [color, setColor] = useState('rgb(255, 255, 255)');
    const [isEraser, setIsEraser] = useState(false);
    const [showColors, setShowColors] = useState(false);
    const [showWidth, setShowWidth] = useState(false);
    const [lineWidth, setLineWidth] = useState(3);
    const [reset, setReset] = useState(false);
    const [dictOfVars, setDictOfVars] = useState<Record<string, string>>({});
    const [latexPosition, setLatexPosition] = useState({ x: 10, y: 200 });
    const [latexExpression, setLatexExpression] = useState<Array<string>>([]);
    const lastPosRef = useRef<{ x: number; y: number } | null>(null);
    const lastMidRef = useRef<{ x: number; y: number } | null>(null);
    const [previewPos, setPreviewPos] = useState<{ x: number; y: number } | null>(null);
    const [previewWidth, setPreviewWidth] = useState<number>(lineWidth);
    const [showPreview, setShowPreview] = useState<boolean>(false);
    const undoStackRef = useRef<ImageData[]>([]);
    const redoStackRef = useRef<ImageData[]>([]);
    const [canUndo, setCanUndo] = useState(false);
    const [canRedo, setCanRedo] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [hasDrawn, setHasDrawn] = useState(false);

    const updateStackStates = useCallback(() => {
        setCanUndo(undoStackRef.current.length > 0);
        setCanRedo(redoStackRef.current.length > 0);
    }, []);
    const colorRef = useRef<HTMLDivElement | null>(null);
    const widthRef = useRef<HTMLDivElement | null>(null);
    const isMac = typeof navigator !== 'undefined' && navigator.platform.toLowerCase().includes('mac');
    const workspaceRef = useRef<HTMLDivElement | null>(null);
    const toolbarRef = useRef<HTMLDivElement | null>(null);
    const logoRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (latexExpression.length > 0 && window.MathJax) {
            setTimeout(() => {
                window.MathJax.Hub.Queue(["Typeset", window.MathJax.Hub]);
            }, 0);
        }
    }, [latexExpression]);

    useEffect(() => {
        resetCanvas();
    }, [latexExpression]);

    useEffect(() => {
        if (reset) {
            resetCanvas();
            setLatexExpression([]);
            setError(null);
            setDictOfVars({});
            setHasDrawn(false);
            setReset(false);
        }
    }, [reset]);

    useEffect(() => {
        const canvas = canvasRef.current;

        if (canvas) {
            const ctx = canvas.getContext('2d');
            if (ctx) {
                canvas.width = window.innerWidth;
                canvas.height = window.innerHeight - canvas.offsetTop;
                ctx.lineCap = 'round';
            }
        }
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.9/MathJax.js?config=TeX-MML-AM_CHTML';
        script.async = true;
        document.head.appendChild(script);

        script.onload = () => {
            if (window.MathJax && window.MathJax.Hub) {
                window.MathJax.Hub.Config({
                    tex2jax: {inlineMath: [['$', '$'], ['\\(', '\\)']]},
                    'HTML-CSS': { availableFonts: [] },
                    messageStyle: 'none'
                });
            }
        };

        return () => {
            if (script.parentNode) document.head.removeChild(script);
        };
    }, []);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (canvas) {
            const ctx = canvas.getContext('2d');
            if (ctx) ctx.lineWidth = lineWidth;
        }
    }, [lineWidth]);


    const resetCanvas = () => {
        const canvas = canvasRef.current;
        if (canvas) {
            const ctx = canvas.getContext('2d');
            if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    };

    const toggleEraser = () => {
        setIsEraser(!isEraser);
        setShowColors(false);
        if (!isEraser) {
            setLineWidth(20);
            setColor('rgb(0, 0, 0)');
        } else {
            setLineWidth(3);
            setColor('rgb(255, 255, 255)');
        }
    };

    const toggleColorPalette = () => {
        setShowColors(!showColors);
        if (isEraser) {
            setIsEraser(false);
            setLineWidth(3);
            setColor('rgb(255, 255, 255)');
        }
    };

    const toggleWidthPalette = () => {
        setShowWidth(!showWidth);
    };

    useEffect(() => {
        const onDocDown = (ev: MouseEvent) => {
            const target = ev.target as Node | null;
            if (showColors && colorRef.current && target && !colorRef.current.contains(target)) {
                setShowColors(false);
            }
            if (showWidth && widthRef.current && target && !widthRef.current.contains(target)) {
                setShowWidth(false);
            }
        };
        document.addEventListener('mousedown', onDocDown);
        return () => document.removeEventListener('mousedown', onDocDown);
    }, [showColors, showWidth]);

    const activePointerId = useRef<number | null>(null);

    const getPointerPos = (e: React.PointerEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        if (!canvas) return { x: 0, y: 0 };
        const rect = canvas.getBoundingClientRect();
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };

    const getStrokeWidthFromEvent = (e: React.PointerEvent<HTMLCanvasElement>) => {
        const pressure = typeof e.pressure === 'number' ? e.pressure : 0;
        const multiplier = pressure > 0 ? 0.5 + pressure * 1.5 : 1;
        return Math.max(1, lineWidth * multiplier);
    };

    const getMidPoint = (p1: { x: number; y: number }, p2: { x: number; y: number }) => ({
        x: (p1.x + p2.x) / 2,
        y: (p1.y + p2.y) / 2,
    });

    const startDrawingPointer = (e: React.PointerEvent<HTMLCanvasElement>) => {
        if (e.pointerType === 'touch' && (!e.isPrimary || (e.width && e.width > 50))) return;

        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        try {
            (e.target as Element).setPointerCapture(e.pointerId);
        } catch {
            // ignore if capture not supported
        }

        activePointerId.current = e.pointerId;
        const pos = getPointerPos(e);
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y);
        ctx.strokeStyle = color;
        ctx.lineWidth = getStrokeWidthFromEvent(e);
        lastPosRef.current = pos;
        lastMidRef.current = pos;
        setIsDrawing(true);
        setShowPreview(true);
        setHasDrawn(true);
        setPreviewPos({ x: e.clientX, y: e.clientY });
        setPreviewWidth(getStrokeWidthFromEvent(e));
    };

    const drawPointer = (e: React.PointerEvent<HTMLCanvasElement>) => {
        if (!isDrawing) return;
        if (activePointerId.current !== null && e.pointerId !== activePointerId.current) return;

        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        if (e.pointerType === 'touch' && e.width && e.width > 50) return;

        const pos = getPointerPos(e);
        ctx.strokeStyle = color;
        ctx.lineWidth = getStrokeWidthFromEvent(e);

        const lastPos = lastPosRef.current;
        const lastMid = lastMidRef.current;
        if (lastPos && lastMid) {
            const mid = getMidPoint(lastPos, pos);
            ctx.beginPath();
            ctx.moveTo(lastMid.x, lastMid.y);
            ctx.quadraticCurveTo(lastPos.x, lastPos.y, mid.x, mid.y);
            ctx.stroke();
            lastMidRef.current = mid;
        } else {
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
            lastMidRef.current = pos;
        }

        lastPosRef.current = pos;
        setPreviewPos({ x: e.clientX, y: e.clientY });
        setPreviewWidth(getStrokeWidthFromEvent(e));
    };

    const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
        setPreviewPos({ x: e.clientX, y: e.clientY });
        setPreviewWidth(getStrokeWidthFromEvent(e));
        if (isDrawing) {
            drawPointer(e);
        }
    };

    const stopDrawingPointer = (e?: React.PointerEvent<HTMLCanvasElement>) => {
        if (e && activePointerId.current !== null) {
            try {
                (e.target as Element).releasePointerCapture(activePointerId.current);
            } catch {
                // ignore
            }
        }
        const canvas = canvasRef.current;
        if (canvas) {
            const ctx = canvas.getContext('2d');
            if (ctx) {
                try {
                    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    undoStackRef.current.push(imageData);
                    redoStackRef.current = [];
                    updateStackStates();
                } catch {
                    // ignore
                }
            }
        }

        activePointerId.current = null;
        setIsDrawing(false);
        setShowPreview(false);
        lastPosRef.current = null;
        lastMidRef.current = null;
    };

    const restoreImageData = (imageData: ImageData) => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.putImageData(imageData, 0, 0);
    };

    const handleUndo = useCallback(() => {
        const canvas = canvasRef.current;
        const ctx = canvas?.getContext('2d');
        if (!canvas || !ctx) return;
        if (undoStackRef.current.length === 0) return;

        const last = undoStackRef.current.pop()!;
        try {
            const current = ctx.getImageData(0, 0, canvas.width, canvas.height);
            redoStackRef.current.push(current);
        } catch {
            // ignore
        }
        restoreImageData(last);
        updateStackStates();
    }, [updateStackStates]);

    const handleRedo = useCallback(() => {
        const canvas = canvasRef.current;
        const ctx = canvas?.getContext('2d');
        if (!canvas || !ctx) return;
        if (redoStackRef.current.length === 0) return;

        const last = redoStackRef.current.pop()!;
        try {
            const current = ctx.getImageData(0, 0, canvas.width, canvas.height);
            undoStackRef.current.push(current);
        } catch {
            // ignore
        }
        restoreImageData(last);
        updateStackStates();
    }, [updateStackStates]);

    useEffect(() => {
        const onKey = (ev: KeyboardEvent) => {
            const ctrl = isMac ? ev.metaKey : ev.ctrlKey;
            if (ctrl && ev.key.toLowerCase() === 'z') {
                ev.preventDefault();
                if (ev.shiftKey) {
                    handleRedo();
                } else {
                    handleUndo();
                }
            }
            if (ctrl && ev.key.toLowerCase() === 'y') {
                ev.preventDefault();
                handleRedo();
            }
        };
        document.addEventListener('keydown', onKey);
        return () => document.removeEventListener('keydown', onKey);
    }, [handleUndo, handleRedo, isMac]);

    const runRoute = async () => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        setIsLoading(true);
        setError(null);

        try {
            const dataUrl = canvas.toDataURL('image/png');
            if (dataUrl.length > MAX_CANVAS_DATA_URL_SIZE) {
                throw new Error('Canvas data too large. Try a smaller drawing.');
            }

            const response = await axios({
                method: 'post',
                url: `${import.meta.env.VITE_API_URL}/calculate`,
                data: {
                    image: dataUrl,
                    dict_of_vars: dictOfVars
                }
            });

            const resp = response.data;

            const validatedData = validateCalculateResponse(resp);
            if (!validatedData || validatedData.length === 0) {
                throw new Error('No valid results returned. Try drawing more clearly.');
            }

            // Handle variable assignments with functional update to avoid stale closure
            validatedData.forEach((data: Response) => {
                if (data.assign === true && isSafeObjectKey(data.expr)) {
                    setDictOfVars((prev) => ({
                        ...prev,
                        [data.expr]: data.result
                    }));
                }
            });

            // Position LaTeX near the center of the drawing
            const ctx = canvas.getContext('2d');
            if (ctx) {
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                let minX = canvas.width, minY = canvas.height, maxX = 0, maxY = 0;

                for (let y = 0; y < canvas.height; y++) {
                    for (let x = 0; x < canvas.width; x++) {
                        const i = (y * canvas.width + x) * 4;
                        if (imageData.data[i + 3] > 0) {
                            minX = Math.min(minX, x);
                            minY = Math.min(minY, y);
                            maxX = Math.max(maxX, x);
                            maxY = Math.max(maxY, y);
                        }
                    }
                }

                setLatexPosition({
                    x: (minX + maxX) / 2,
                    y: (minY + maxY) / 2
                });
            }

            // Batch all results into a single setLatexExpression call to avoid
            // the canvas clearing race condition (each call previously triggered
            // resetCanvas via useEffect, clearing the canvas N times)
            const allLatex = validatedData.map((d: Response) => {
                const cleanExpr = sanitizeLatex(d.expr);
                const cleanAnswer = sanitizeLatex(d.result);
                return `\\(\\LARGE{${cleanExpr} = ${cleanAnswer}}\\)`;
            });
            setLatexExpression((prev) => [...prev, ...allLatex]);

        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'An error occurred while analyzing the image.';
            setError(message);
            console.error('runRoute error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const downloadDataUrl = (dataUrl: string, filename: string) => {
        const a = document.createElement('a');
        a.href = dataUrl;
        a.download = sanitizeFilename(filename);
        document.body.appendChild(a);
        a.click();
        a.remove();
    };

    const exportWorkspaceAsImage = async (hideUi = false) => {
        const node = workspaceRef.current || document.body;
        const bg = node ? window.getComputedStyle(node).backgroundColor : '#ffffff';
        const toHide: HTMLElement[] = [];
        try {
            if (hideUi) {
                if (toolbarRef.current) toHide.push(toolbarRef.current);
                if (logoRef.current) toHide.push(logoRef.current);
                toHide.forEach((el) => { (el.style as CSSStyleDeclaration).visibility = 'hidden'; });
            }

            const snap = await html2canvas(node as HTMLElement, { backgroundColor: bg, useCORS: true, scale: window.devicePixelRatio });
            return snap.toDataURL('image/png');
        } catch {
            const canvas = canvasRef.current;
            if (!canvas) return null;
            return canvas.toDataURL('image/png');
        } finally {
            if (hideUi) toHide.forEach((el) => { (el.style as CSSStyleDeclaration).visibility = ''; });
        }
    };

    const handleExport = async () => {
        const dataUrl = await exportWorkspaceAsImage(true);
        if (dataUrl) downloadDataUrl(dataUrl, `solvo-${Date.now()}.png`);
    };

    const handleShare = async () => {
        const dataUrl = await exportWorkspaceAsImage(true);
        if (!dataUrl) return;

        let blob: Blob | null = null;
        try {
            const res = await fetch(dataUrl);
            blob = await res.blob();
        } catch {
            handleExport();
            return;
        }

        // Validate file before upload
        if (blob) {
            const file = new File([blob], `solvo-${Date.now()}.png`, { type: 'image/png' });
            const validation = validateFileUpload(file);
            if (!validation.valid) {
                setError(validation.error || 'Invalid file');
                return;
            }
        }

        try {
            const file = new File([blob!], `solvo-${Date.now()}.png`, { type: 'image/png' });
            const form = new FormData();
            form.append('file', file);
            const resp = await axios.post(`${import.meta.env.VITE_API_URL}/upload`, form, { headers: { 'Content-Type': 'multipart/form-data' } });
            const url = resp?.data?.url;
            if (url) {
                try { await navigator.clipboard.writeText(url); } catch {
                    // ignore clipboard errors
                }
                window.alert('Shareable link copied to clipboard:\n' + url);
                return;
            }
        } catch {
            // upload failed, fall through to Web Share API
        }

        try {
            const shareNav = navigator as unknown as { canShare?: (d: { files?: File[] }) => boolean; share?: (data: { files?: File[]; title?: string }) => Promise<void> };
            const file = new File([blob!], `solvo-${Date.now()}.png`, { type: 'image/png' });
            if (shareNav.canShare && shareNav.canShare({ files: [file] })) {
                await (navigator as unknown as { share: (data: { files: File[]; title?: string }) => Promise<void> }).share({ files: [file], title: 'Solvo drawing' });
                return;
            }
            if (shareNav.share) {
                await (navigator as unknown as { share: (data: { files: File[]; title?: string }) => Promise<void> }).share({ files: [file], title: 'Solvo drawing' });
                return;
            }
        } catch {
            // ignore
        }

        handleExport();
    };

    return (
        <>
            <div ref={logoRef} className="hidden md:block fixed top-0 left-16 z-30">
                <img src={logo} alt="Logo" className="h-24 w-36 md:h-24 md:w-36 hover:scale-110 transition-transform duration-200 shadow-lg" />
            </div>
            <div ref={toolbarRef} className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 flex items-center gap-2 bg-gray-900/50 p-2 rounded-lg backdrop-blur-sm">
                <Button
                    onClick={() => setReset(true)}
                    className="bg-transparent hover:bg-gray-100 text-white p-2 rounded-lg transition-all duration-200"
                    variant="ghost"
                    size="icon"
                >
                    <RotateCcw className="h-5 w-5" />
                </Button>
                <div className="relative">
                    <Button
                        onClick={handleUndo}
                        className={`bg-transparent hover:bg-gray-100 text-white p-2 rounded-lg transition-all duration-200 ${canUndo ? '' : 'opacity-40 pointer-events-none'}`}
                        variant="ghost"
                        size="icon"
                        title={isMac ? 'Undo (⌘+Z)' : 'Undo (Ctrl+Z)'}
                    >
                        <CornerUpLeft className="h-5 w-5" />
                    </Button>
                </div>
                <div className="relative">
                    <Button
                        onClick={handleRedo}
                        className={`bg-transparent hover:bg-gray-100 text-white p-2 rounded-lg transition-all duration-200 ${canRedo ? '' : 'opacity-40 pointer-events-none'}`}
                        variant="ghost"
                        size="icon"
                        title={isMac ? 'Redo (⌘+Shift+Z / ⌘+Y)' : 'Redo (Ctrl+Shift+Z / Ctrl+Y)'}
                    >
                        <CornerUpRight className="h-5 w-5" />
                    </Button>
                </div>
                
                <div className="relative" ref={colorRef}>
                    <Button
                        onClick={toggleColorPalette}
                        className={`bg-transparent hover:bg-gray-800 text-white p-2 rounded-lg transition-all duration-200 ${showColors ? 'bg-gray-800' : ''}`}
                        variant="ghost"
                        size="icon"
                    >
                        <Palette className="h-5 w-5" style={{ color: color === 'rgb(0, 0, 0)' ? 'white' : color }} />
                    </Button>
                    {showColors && (
                        <div className="absolute top-full left-0 mt-2 p-2 bg-gray-900/50 backdrop-blur-sm rounded-lg flex gap-1">
                            {SWATCHES.map((swatch) => (
                                <ColorSwatch
                                    key={swatch}
                                    color={swatch}
                                    onClick={() => setColor(swatch)}
                                    className="cursor-pointer hover:scale-110 transition-transform"
                                />
                            ))}
                        </div>
                    )}
                </div>
                <div className="relative" ref={widthRef}>
                    <Button
                        onClick={toggleWidthPalette}
                        className={`bg-transparent hover:bg-gray-800 text-white p-2 rounded-lg transition-all duration-200 ${showWidth ? 'bg-gray-800' : ''}`}
                        variant="ghost"
                        size="icon"
                    >
                        <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'transparent', border: '2px solid white' }} />
                    </Button>
                    {showWidth && (
                        <div className="absolute top-full left-0 mt-2 p-2 bg-gray-900/50 backdrop-blur-sm rounded-lg flex items-center gap-2">
                            <input
                                aria-label="Line width"
                                type="range"
                                min={1}
                                max={50}
                                value={lineWidth}
                                onChange={(ev) => setLineWidth(Number((ev.target as HTMLInputElement).value))}
                                className="w-28"
                            />
                            <div className="text-white text-sm" style={{ minWidth: 28, textAlign: 'center' }}>{lineWidth}</div>
                        </div>
                    )}
                </div>

                <Button
                    onClick={toggleEraser}
                    className={`bg-transparent hover:bg-gray-100 text-white p-2 rounded-lg transition-all duration-200 ${isEraser ? 'bg-gray-800' : ''}`}
                    variant="ghost"
                    size="icon"
                >
                    {isEraser ? <Pencil className="h-5 w-5" /> : <Eraser className="h-5 w-5" />}
                </Button>

                <Button
                    onClick={runRoute}
                    disabled={isLoading}
                    className={`bg-blue-600 hover:bg-blue-700 text-white p-2 rounded-lg transition-all duration-200 disabled:opacity-50 ${!hasDrawn && !isLoading ? 'animate-pulse' : ''}`}
                    size="icon"
                    title={!hasDrawn ? 'Draw something, then tap to solve' : 'Solve'}
                >
                    {isLoading ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                        <Play className="h-5 w-5" />
                    )}
                </Button>
                <Button
                    onClick={handleExport}
                    className="bg-transparent hover:bg-gray-100 text-white p-2 rounded-lg transition-all duration-200"
                    variant="ghost"
                    size="icon"
                    title="Download PNG"
                >
                    <Download className="h-5 w-5" />
                </Button>
                <Button
                    onClick={handleShare}
                    className="bg-transparent hover:bg-gray-100 text-white p-2 rounded-lg transition-all duration-200"
                    variant="ghost"
                    size="icon"
                    title="Share"
                >
                    <Share2 className="h-5 w-5" />
                </Button>
            </div>

            {error && (
                <div className="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 bg-red-900/80 text-red-200 px-4 py-2 rounded-lg backdrop-blur-sm text-sm max-w-md text-center">
                    {error}
                    <button
                        onClick={() => setError(null)}
                        className="ml-2 text-red-400 hover:text-red-200"
                    >
                        ✕
                    </button>
                </div>
            )}

            <canvas
                ref={canvasRef}
                id='canvas'
                className='absolute top-0 left-0 w-full h-full bg-black'
                style={{ touchAction: 'none', cursor: 'none', zIndex: 0, pointerEvents: 'auto' }}
                onPointerDown={startDrawingPointer}
                onPointerMove={handlePointerMove}
                onPointerUp={stopDrawingPointer}
                onPointerCancel={stopDrawingPointer}
            />

            {previewPos && (
                <div
                    style={{
                        position: 'fixed',
                        left: previewPos.x,
                        top: previewPos.y,
                        transform: 'translate(-50%, -50%)',
                        pointerEvents: 'none',
                        width: lineWidth * 2,
                        height: lineWidth * 2,
                        borderRadius: '50%',
                        border: '2px solid rgba(255,255,255,0.9)',
                        background: 'transparent',
                        mixBlendMode: 'difference',
                        zIndex: 60,
                    }}
                />
            )}
            {showPreview && previewPos && (
                <div
                    aria-hidden
                    style={{
                        position: 'fixed',
                        left: previewPos.x,
                        top: previewPos.y,
                        transform: 'translate(-50%, -50%)',
                        pointerEvents: 'none',
                        width: previewWidth * 2,
                        height: previewWidth * 2,
                        borderRadius: '50%',
                        background: color,
                        boxShadow: '0 0 8px rgba(0,0,0,0.6)',
                        zIndex: 60,
                    }}
                />
            )}

            {latexExpression && latexExpression.map((latex, index) => (
                <Draggable
                    key={index}
                    defaultPosition={latexPosition}
                    onStop={(_, data) => setLatexPosition({ x: data.x, y: data.y })}
                >
                    <div className="absolute p-2 text-white rounded shadow-md">
                        <div className="latex-content">{latex}</div>
                    </div>
                </Draggable>
            ))}
        </>
    );
}
