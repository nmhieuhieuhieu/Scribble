import { useEffect, useRef } from 'react';

interface Star {
  x: number;
  y: number;
  size: number;
  color: string;
  twinkleSpeed: number;
  twinklePhase: number;
}

interface SparkleStar {
  xRatio: number;
  yRatio: number;
  size: number;
  pulseSpeed: number;
  phase: number;
}

export function GalaxySoundwaveBg() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    let animId = 0;
    let width = 0;
    let height = 0;
    let dpr = 1;

    // ── 1. Delicate Twinkling Stars (Các vì tinh tú) ──
    const starColors = ['#ffffff', '#ffffff', '#fdf4ff', '#fae8ff', '#e9d5ff', '#d8b4fe', '#c084fc', '#fbcfe8'];
    const stars: Star[] = [];
    const starCount = 110;

    const initStars = (w: number, h: number) => {
      stars.length = 0;
      for (let i = 0; i < starCount; i++) {
        stars.push({
          x: Math.random() * w,
          y: Math.random() * h,
          size: Math.random() * 1.5 + 0.6,
          color: starColors[Math.floor(Math.random() * starColors.length)],
          twinkleSpeed: Math.random() * 0.025 + 0.012,
          twinklePhase: Math.random() * Math.PI * 2,
        });
      }
    };

    // ── 2. Subtle 4-Point Sparkling Stars ──
    const sparkles: SparkleStar[] = [
      { xRatio: 0.82, yRatio: 0.18, size: 20, pulseSpeed: 0.025, phase: 0 },
      { xRatio: 0.22, yRatio: 0.25, size: 16, pulseSpeed: 0.03, phase: 1.6 },
      { xRatio: 0.75, yRatio: 0.55, size: 18, pulseSpeed: 0.022, phase: 3.2 },
      { xRatio: 0.14, yRatio: 0.68, size: 15, pulseSpeed: 0.028, phase: 4.5 },
      { xRatio: 0.88, yRatio: 0.82, size: 16, pulseSpeed: 0.024, phase: 2.1 },
      { xRatio: 0.48, yRatio: 0.15, size: 14, pulseSpeed: 0.032, phase: 0.8 },
    ];

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.parentElement?.clientWidth || window.innerWidth;
      height = canvas.parentElement?.clientHeight || window.innerHeight;

      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      initStars(width, height);
    };

    window.addEventListener('resize', resize);
    resize();

    let t = 0;

    const render = () => {
      t += 0.016;

      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      // ── A. Nền tím nhạt thanh lịch (Soft Light Purple Gradient) ──
      const bgGrad = ctx.createLinearGradient(0, 0, width, height);
      bgGrad.addColorStop(0, '#faf5ff');    // Trắng phớt tím rất nhẹ, trong trẻo
      bgGrad.addColorStop(0.35, '#f3e8ff'); // Tím phấn pastel dịu mắt
      bgGrad.addColorStop(0.70, '#e9d5ff'); // Tím nhạt lavender TPBank
      bgGrad.addColorStop(1, '#ddd6fe');    // Tím ánh ngọc êm đềm
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // Vầng sáng tím hồng rất nhẹ tỏa từ góc trên
      const glowGrad = ctx.createRadialGradient(
        width * 0.25, height * 0.2, 20,
        width * 0.25, height * 0.2, width * 0.65
      );
      glowGrad.addColorStop(0, 'rgba(245, 208, 254, 0.45)');
      glowGrad.addColorStop(0.5, 'rgba(233, 213, 255, 0.25)');
      glowGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = glowGrad;
      ctx.fillRect(0, 0, width, height);

      // ── B. Các vì tinh tú lấp lánh (Twinkling Stars) ──
      for (const s of stars) {
        s.twinklePhase += s.twinkleSpeed;
        const curAlpha = 0.35 + Math.sin(s.twinklePhase) * 0.55;
        if (curAlpha <= 0) continue;

        ctx.fillStyle = s.color;
        ctx.globalAlpha = Math.max(0.1, Math.min(1, curAlpha));
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      // ── C. Những vì sao 4 cánh tỏa sáng dịu dàng (Sparkling Cross Stars) ──
      for (const sp of sparkles) {
        sp.phase += sp.pulseSpeed;
        const scale = 0.75 + Math.sin(sp.phase) * 0.35;
        const cx = sp.xRatio * width;
        const cy = sp.yRatio * height;
        const armLen = sp.size * scale;

        ctx.save();
        ctx.translate(cx, cy);

        // Hào quang mềm mại
        const halo = ctx.createRadialGradient(0, 0, 1, 0, 0, armLen * 1.4);
        halo.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
        halo.addColorStop(0.35, 'rgba(192, 132, 252, 0.45)');
        halo.addColorStop(1, 'transparent');
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(0, 0, armLen * 1.4, 0, Math.PI * 2);
        ctx.fill();

        // Tia sáng ngang
        const hRay = ctx.createLinearGradient(-armLen * 1.8, 0, armLen * 1.8, 0);
        hRay.addColorStop(0, 'rgba(255, 255, 255, 0)');
        hRay.addColorStop(0.5, '#ffffff');
        hRay.addColorStop(1, 'rgba(255, 255, 255, 0)');
        ctx.fillStyle = hRay;
        ctx.fillRect(-armLen * 1.8, -1, armLen * 3.6, 2);

        // Tia sáng dọc
        const vRay = ctx.createLinearGradient(0, -armLen * 1.8, 0, armLen * 1.8);
        vRay.addColorStop(0, 'rgba(255, 255, 255, 0)');
        vRay.addColorStop(0.5, '#ffffff');
        vRay.addColorStop(1, 'rgba(255, 255, 255, 0)');
        ctx.fillStyle = vRay;
        ctx.fillRect(-1, -armLen * 1.8, 2, armLen * 3.6);

        // Tâm hạt sao
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(0, 0, 1.6, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
      }

      ctx.restore();

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <div className="galaxy-soundwave-bg" aria-hidden="true">
      <canvas ref={canvasRef} className="galaxy-soundwave-canvas" />
    </div>
  );
}
