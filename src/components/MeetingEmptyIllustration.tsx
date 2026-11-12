export function MeetingEmptyIllustration() {
  return (
    <div className="empty-illustration-wrap">
      <svg
        width="230"
        height="185"
        viewBox="0 0 230 185"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="empty-illustration-svg"
        aria-hidden="true"
      >
        <defs>
          {/* Background Aura Glow */}
          <radialGradient
            id="aura-glow"
            cx="50%"
            cy="50%"
            r="50%"
            fx="48%"
            fy="48%"
          >
            <stop offset="0%" stopColor="#bfdbfe" stopOpacity="0.45" />
            <stop offset="40%" stopColor="#c7d2fe" stopOpacity="0.35" />
            <stop offset="70%" stopColor="#e9d5ff" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#ede9fe" stopOpacity="0" />
          </radialGradient>

          {/* Soundwave Gradient */}
          <linearGradient id="wave-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#a855f7" />
            <stop offset="50%" stopColor="#c084fc" />
            <stop offset="100%" stopColor="#f472b6" />
          </linearGradient>

          {/* Mic Gradients */}
          <linearGradient id="mic-head-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#581c87" />
            <stop offset="25%" stopColor="#6b21a8" />
            <stop offset="60%" stopColor="#8b5cf6" />
            <stop offset="90%" stopColor="#6b21a8" />
            <stop offset="100%" stopColor="#4c1d95" />
          </linearGradient>

          <linearGradient id="mic-stand-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#3b0764" />
            <stop offset="50%" stopColor="#581c87" />
            <stop offset="100%" stopColor="#3b0764" />
          </linearGradient>

          <linearGradient id="calendar-header-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#ea580c" />
            <stop offset="100%" stopColor="#f97316" />
          </linearGradient>

          {/* TPBank 3D Badge Gradients */}
          <linearGradient id="tpb-mini-orange" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#fb923c" />
            <stop offset="100%" stopColor="#ea580c" />
          </linearGradient>

          <linearGradient id="tpb-mini-purple" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#a855f7" />
            <stop offset="100%" stopColor="#581c87" />
          </linearGradient>

          {/* Soft Drop Shadows */}
          <filter id="soft-card-shadow" x="-20%" y="-15%" width="140%" height="135%">
            <feDropShadow dx="0" dy="5" stdDeviation="7" floodColor="#3730a3" floodOpacity="0.1" />
          </filter>
          <filter id="mic-main-shadow" x="-25%" y="-15%" width="150%" height="135%">
            <feDropShadow dx="0" dy="8" stdDeviation="10" floodColor="#2e1065" floodOpacity="0.18" />
          </filter>
        </defs>

        {/* 1. Backdrop Aura */}
        <circle cx="115" cy="92" r="76" fill="url(#aura-glow)" />

        {/* 2. Soundwaves on left */}
        <g opacity="0.9">
          <rect x="42" y="88" width="3.5" height="18" rx="1.75" fill="url(#wave-grad)" />
          <rect x="49" y="76" width="3.5" height="40" rx="1.75" fill="url(#wave-grad)" />
          <rect x="56" y="66" width="3.5" height="60" rx="1.75" fill="url(#wave-grad)" />
          <rect x="63" y="78" width="3.5" height="36" rx="1.75" fill="url(#wave-grad)" />
          <rect x="70" y="89" width="3.5" height="14" rx="1.75" fill="url(#wave-grad)" />
        </g>

        {/* 3. Flip Calendar (Top-Right) */}
        <g filter="url(#soft-card-shadow)">
          {/* White calendar page */}
          <rect x="126" y="38" width="58" height="54" rx="7" fill="#ffffff" stroke="#e2e8f0" strokeWidth="1" />
          {/* Orange top bar */}
          <path
            d="M126 45C126 41.134 129.134 38 133 38H177C180.866 38 184 41.134 184 45V53H126V45Z"
            fill="url(#calendar-header-grad)"
          />
          {/* Top binder rings */}
          <rect x="138" y="33" width="4.5" height="9" rx="2.25" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.5" />
          <rect x="153" y="33" width="4.5" height="9" rx="2.25" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.5" />
          <rect x="168" y="33" width="4.5" height="9" rx="2.25" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.5" />

          {/* Calendar Day Grid (4 columns × 3 rows) */}
          <rect x="134" y="59" width="6" height="5" rx="1.5" fill="#e2e8f0" />
          <rect x="145" y="59" width="6" height="5" rx="1.5" fill="#e2e8f0" />
          <rect x="156" y="59" width="6" height="5" rx="1.5" fill="#38bdf8" />
          <rect x="167" y="59" width="6" height="5" rx="1.5" fill="#e2e8f0" />

          <rect x="134" y="68" width="6" height="5" rx="1.5" fill="#e2e8f0" />
          <rect x="145" y="68" width="6" height="5" rx="1.5" fill="#818cf8" />
          <rect x="156" y="68" width="6" height="5" rx="1.5" fill="#e2e8f0" />
          <rect x="167" y="68" width="6" height="5" rx="1.5" fill="#e2e8f0" />

          <rect x="134" y="77" width="6" height="5" rx="1.5" fill="#e2e8f0" />
          <rect x="145" y="77" width="6" height="5" rx="1.5" fill="#e2e8f0" />
          <rect x="156" y="77" width="6" height="5" rx="1.5" fill="#fb923c" />
          <rect x="167" y="77" width="6" height="5" rx="1.5" fill="#e2e8f0" />
        </g>

        {/* 4. Spiral Notepad (Right, slightly behind mic) */}
        <g filter="url(#soft-card-shadow)" transform="rotate(4 156 108)">
          <rect x="130" y="78" width="56" height="72" rx="7" fill="#ffffff" stroke="#cbd5e1" strokeWidth="1.2" />
          {/* Wire binding along left edge */}
          <path d="M138 74 C136 71 133 73 133 76 C133 79 136 80 138 80" stroke="#475569" strokeWidth="2" strokeLinecap="round" />
          <path d="M148 74 C146 71 143 73 143 76 C143 79 146 80 148 80" stroke="#475569" strokeWidth="2" strokeLinecap="round" />
          <path d="M158 74 C156 71 153 73 153 76 C153 79 156 80 158 80" stroke="#475569" strokeWidth="2" strokeLinecap="round" />
          <path d="M168 74 C166 71 163 73 163 76 C163 79 166 80 168 80" stroke="#475569" strokeWidth="2" strokeLinecap="round" />

          {/* Ruled lines */}
          <line x1="138" y1="92" x2="176" y2="92" stroke="#cbd5e1" strokeWidth="2" strokeLinecap="round" />
          <line x1="138" y1="102" x2="172" y2="102" stroke="#cbd5e1" strokeWidth="2" strokeLinecap="round" />
          <line x1="138" y1="112" x2="176" y2="112" stroke="#cbd5e1" strokeWidth="2" strokeLinecap="round" />
          <line x1="138" y1="122" x2="166" y2="122" stroke="#cbd5e1" strokeWidth="2" strokeLinecap="round" />
          <line x1="138" y1="132" x2="174" y2="132" stroke="#e2e8f0" strokeWidth="2" strokeLinecap="round" />

          {/* Dots/bullets */}
          <circle cx="134" cy="92" r="1.5" fill="#a855f7" />
          <circle cx="134" cy="102" r="1.5" fill="#f97316" />
          <circle cx="134" cy="112" r="1.5" fill="#38bdf8" />
        </g>

        {/* 5. 3D Purple Studio Microphone */}
        <g filter="url(#mic-main-shadow)">
          {/* Base disc */}
          <ellipse cx="111" cy="158" rx="26" ry="8" fill="#312e81" />
          <ellipse cx="111" cy="155" rx="23" ry="6.5" fill="#4c1d95" />
          <ellipse cx="111" cy="153" rx="18" ry="4.5" fill="#6d28d9" opacity="0.6" />

          {/* Vertical stem */}
          <rect x="108" y="122" width="6" height="34" rx="3" fill="url(#mic-stand-grad)" />

          {/* U-cradle mount */}
          <path
            d="M91 92 C91 127, 131 127, 131 92"
            fill="none"
            stroke="#4338ca"
            strokeWidth="5"
            strokeLinecap="round"
          />
          {/* Swivel knobs */}
          <circle cx="91" cy="92" r="3.5" fill="#6d28d9" stroke="#312e81" strokeWidth="1" />
          <circle cx="131" cy="92" r="3.5" fill="#6d28d9" stroke="#312e81" strokeWidth="1" />

          {/* Capsule dome */}
          <rect x="96" y="60" width="30" height="55" rx="15" fill="url(#mic-head-grad)" />
          {/* Specular highlight */}
          <path
            d="M100 66 C100 63 103 62 106 62 C104 65 102 70 102 82 C102 93 104 98 106 100 H101 C100 97 100 85 100 66 Z"
            fill="#ffffff"
            opacity="0.32"
          />

          {/* Upper Grille Slits */}
          <line x1="102" y1="69" x2="120" y2="69" stroke="#ffffff" strokeWidth="1.6" strokeLinecap="round" opacity="0.55" />
          <line x1="101" y1="75" x2="121" y2="75" stroke="#ffffff" strokeWidth="1.6" strokeLinecap="round" opacity="0.55" />
          <line x1="101" y1="81" x2="121" y2="81" stroke="#ffffff" strokeWidth="1.6" strokeLinecap="round" opacity="0.55" />

          {/* Center divider band */}
          <rect x="95" y="87" width="32" height="4.5" rx="1.5" fill="#e2e8f0" />

          {/* Lower Grille Slits */}
          <line x1="101" y1="98" x2="121" y2="98" stroke="#ffffff" strokeWidth="1.6" strokeLinecap="round" opacity="0.35" />
          <line x1="102" y1="104" x2="120" y2="104" stroke="#ffffff" strokeWidth="1.6" strokeLinecap="round" opacity="0.35" />
        </g>

        {/* 6. TPBank 3D Origami Emblem (At front-left of mic base) */}
        <g filter="url(#soft-card-shadow)">
          <ellipse cx="91" cy="152" rx="15" ry="4.5" fill="#1e1b4b" opacity="0.28" />
          {/* 3D Folded Triangle */}
          <path
            d="M75 137 L102 128 C104 127 106 129 105 131 L98 153 C97 155 94 156 93 155 L75 142 C73 141 73 138 75 137 Z"
            fill="url(#tpb-mini-orange)"
          />
          <path
            d="M75 142 L93 155 C94 156 93 159 91 159 L78 160 C75 160 73 157 74 154 L75 142 Z"
            fill="url(#tpb-mini-purple)"
          />
          <polygon points="84,139 94,135 89,147" fill="#ffffff" />
        </g>
      </svg>
    </div>
  );
}
