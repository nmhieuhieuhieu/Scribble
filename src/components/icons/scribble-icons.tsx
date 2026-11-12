import type { SVGProps } from 'react';
import {
  ArrowDown,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronUp,
  Circle,
  CircleAlert,
  CircleCheck,
  CircleX,
  Copy,
  Download,
  Ellipsis,
  Eye,
  EyeOff,
  FileText,
  Info,
  Languages,
  LoaderCircle,
  Mic,
  Monitor,
  Moon,
  NotebookText,
  Paperclip,
  Pause,
  Pencil,
  PenTool,
  Play,
  Plus,
  Search,
  Settings,
  Sliders,
  SlidersHorizontal,
  Square,
  Sun,
  Trash2,
  TriangleAlert,
  Upload,
  User,
  WifiOff,
  X,
  type LucideIcon,
} from 'lucide-react';

/**
 * TPBank Voicebot icon set — powered by Lucide Icons (https://lucide.dev/icons/).
 */
export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'width' | 'height'> {
  size?: number;
  strokeWidth?: number | string;
}

function wrapLucide(Icon: LucideIcon, defaultFilled = false) {
  return function WrappedLucideIcon({ size = 16, strokeWidth = 1.8, fill, ...rest }: IconProps) {
    return (
      <Icon
        size={size}
        strokeWidth={strokeWidth}
        fill={fill ?? (defaultFilled ? 'currentColor' : 'none')}
        aria-hidden="true"
        {...rest}
      />
    );
  };
}

// ── Recording & audio ──────────────────────────────────────────────
export const IconMic = wrapLucide(Mic);
export const IconRecord = wrapLucide(Circle, true);
export const IconStop = wrapLucide(Square, true);
export const IconPlay = wrapLucide(Play, true);
export const IconPause = wrapLucide(Pause, true);
export const IconTranslate = wrapLucide(Languages);
export const IconSpeaker = wrapLucide(User);

// ── Navigation & chrome ────────────────────────────────────────────
export const IconSettings = wrapLucide(SlidersHorizontal);
export const IconGear = wrapLucide(Settings);
export const IconSliders = wrapLucide(Sliders);
export const IconSun = wrapLucide(Sun);
export const IconMoon = wrapLucide(Moon);
export const IconClose = wrapLucide(X);
export const IconPlus = wrapLucide(Plus);
export const IconCheck = wrapLucide(Check);
export const IconChevronDown = wrapLucide(ChevronDown);
export const IconChevronUp = wrapLucide(ChevronUp);
export const IconChevronLeft = wrapLucide(ChevronLeft);
export const IconArrowDown = wrapLucide(ArrowDown);
export const IconDots = wrapLucide(Ellipsis);
export const IconSpinner = wrapLucide(LoaderCircle);

// ── Actions ────────────────────────────────────────────────────────
export const IconDownload = wrapLucide(Download);
export const IconUpload = wrapLucide(Upload);
export const IconSearch = wrapLucide(Search);
export const IconEdit = wrapLucide(Pencil);
export const IconTrash = wrapLucide(Trash2);
export const IconCopy = wrapLucide(Copy);
export const IconPaperclip = wrapLucide(Paperclip);
export const IconEye = wrapLucide(Eye);
export const IconEyeOff = wrapLucide(EyeOff);

// ── Documents ──────────────────────────────────────────────────────
export const IconMinutes = wrapLucide(NotebookText);
export const IconNib = wrapLucide(PenTool);
export const IconPage = wrapLucide(FileText);

// ── Status ─────────────────────────────────────────────────────────
export const IconWarning = wrapLucide(TriangleAlert);
export const IconAlert = wrapLucide(CircleAlert);
export const IconInfo = wrapLucide(Info);
export const IconErrorCircle = wrapLucide(CircleX);
export const IconCheckCircle = wrapLucide(CircleCheck);
export const IconWifiOff = wrapLucide(WifiOff);
export const IconSystem = wrapLucide(Monitor);

export function IconTPBank({ size = 20, className = '', ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...props}
    >
      <defs>
        <linearGradient id="tpb-logo-orange-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FFA028" />
          <stop offset="55%" stopColor="#FF7A00" />
          <stop offset="100%" stopColor="#E65100" />
        </linearGradient>
      </defs>
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M20 16.5C16.5 14.4 12 16.9 12 21V79C12 83.1 16.5 85.6 20 83.5L84.5 54.5C88.2 52.4 88.2 47.6 84.5 45.5L20 16.5ZM26 34.5L62 50L26 65.5V34.5Z"
        fill="url(#tpb-logo-orange-gradient)"
      />
    </svg>
  );
}
