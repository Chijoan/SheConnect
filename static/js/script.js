console.log("SheConnect homepage loaded.");

// Emergency Help "Quick Exit" — immediately leaves this page and replaces it
// in browser history with a neutral website, so it cannot be reopened with
// the Back button.
const quickExitButton = document.getElementById("quickExitBtn");

if (quickExitButton) {
    quickExitButton.addEventListener("click", () => {
        window.location.replace("https://www.google.com");
    });
}

// Toggle mobile navigation menu
const navToggle = document.getElementById("navToggle");
const navLinks = document.getElementById("navLinks");

if (navToggle && navLinks) {
    const closeNavMenu = () => {
        navLinks.classList.remove("open");
        navToggle.classList.remove("open");
        navToggle.setAttribute("aria-expanded", "false");
    };

    navToggle.addEventListener("click", () => {
        const isOpen = navLinks.classList.toggle("open");
        navToggle.classList.toggle("open", isOpen);
        navToggle.setAttribute("aria-expanded", String(isOpen));
    });

    // Close the panel once a link inside it is actually chosen, so it
    // never stays open (or reopens via the back/forward cache) after
    // navigating to the new page.
    navLinks.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", closeNavMenu);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeNavMenu();
        }
    });
}

// Language selector dropdown — opens on click, closes on an outside click,
// on Escape, or after a language is chosen.
const langSelector = document.getElementById("langSelector");
const langToggle = document.getElementById("langToggle");

if (langSelector && langToggle) {
    const closeLangMenu = () => {
        langSelector.classList.remove("open");
        langToggle.setAttribute("aria-expanded", "false");
    };

    langToggle.addEventListener("click", (event) => {
        event.stopPropagation();
        const isOpen = langSelector.classList.toggle("open");
        langToggle.setAttribute("aria-expanded", String(isOpen));
    });

    document.addEventListener("click", (event) => {
        if (!langSelector.contains(event.target)) {
            closeLangMenu();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeLangMenu();
        }
    });
}

// Prevent accidental double form submission (e.g. a fast double-click on
// "Create account" or "Log in") by disabling the submit button after the
// first click. This does not block the submission itself — the form still
// posts normally — it just stops a second, duplicate request from firing.
document.querySelectorAll(".auth-form").forEach((form) => {
    form.addEventListener("submit", () => {
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton && !submitButton.disabled) {
            submitButton.disabled = true;
            submitButton.textContent = "Please wait...";
        }
    });
});

// Live password-strength feedback for the registration form.
// This is a UX aid only — the backend re-validates every rule independently.
const passwordInput = document.getElementById("password");
const strengthBar = document.getElementById("strengthBar");
const strengthLabel = document.getElementById("strengthLabel");
const passwordRequirements = document.getElementById("passwordRequirements");

if (passwordInput && strengthBar && strengthLabel && passwordRequirements) {
    const rules = {
        length: (value) => value.length >= 8,
        uppercase: (value) => /^[A-Z]/.test(value),
        lowercase: (value) => /[a-z]/.test(value),
        number: (value) => /\d/.test(value),
        symbol: (value) => /[^A-Za-z0-9]/.test(value),
    };

    // Falls back to English if the server didn't provide translated labels.
    const labels = window.STRENGTH_LABELS || {
        veryWeak: "Very Weak",
        weak: "Weak",
        medium: "Medium",
        strong: "Strong",
        veryStrong: "Very Strong",
    };

    const levels = [
        { color: "#e63946", label: labels.veryWeak },
        { color: "#e63946", label: labels.veryWeak },
        { color: "#fb8c00", label: labels.weak },
        { color: "#fdd835", label: labels.medium },
        { color: "#8bc34a", label: labels.strong },
        { color: "#2e7d32", label: labels.veryStrong },
    ];

    const updatePasswordStrength = () => {
        const value = passwordInput.value;
        let metCount = 0;

        Object.keys(rules).forEach((ruleName) => {
            const met = rules[ruleName](value);
            if (met) metCount += 1;

            const item = passwordRequirements.querySelector(`[data-rule="${ruleName}"]`);
            if (item) {
                item.classList.toggle("requirement-met", met);
            }
        });

        if (value.length === 0) {
            strengthBar.style.width = "0%";
            strengthBar.style.backgroundColor = "transparent";
            strengthLabel.textContent = "";
            return;
        }

        const level = levels[metCount];
        strengthBar.style.width = `${(metCount / 5) * 100}%`;
        strengthBar.style.backgroundColor = level.color;
        strengthLabel.textContent = level.label;
        strengthLabel.style.color = level.color;
    };

    passwordInput.addEventListener("input", updatePasswordStrength);
    updatePasswordStrength();
}

// Show/Hide toggle for password fields
const togglePasswordButtons = document.querySelectorAll(".toggle-password");

togglePasswordButtons.forEach((button) => {
    const showText = button.dataset.showText || "Show";
    const hideText = button.dataset.hideText || "Hide";

    button.addEventListener("click", () => {
        const target = document.getElementById(button.dataset.target);
        if (!target) return;

        const isCurrentlyHidden = target.type === "password";
        target.type = isCurrentlyHidden ? "text" : "password";
        button.textContent = isCurrentlyHidden ? hideText : showText;
        button.setAttribute("aria-label", isCurrentlyHidden ? hideText : showText);
        button.setAttribute("aria-pressed", String(isCurrentlyHidden));
    });
});

// One-time post-registration celebration: full-screen confetti, large
// party-face emojis, small sparkles, and a centred welcome card. The server
// only renders #celebration/#celebrationCard into the page for the single
// request right after a successful registration (see the `just_registered`
// session flag in app.py, which is popped the instant it is read — never set
// by login) — so a refresh, a later visit, or a normal login never includes
// these elements and this block simply does nothing.
const celebrationContainer = document.getElementById("celebration");
const celebrationCard = document.getElementById("celebrationCard");

if (celebrationContainer || celebrationCard) {
    const prefersReducedMotion =
        window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (celebrationCard) {
        window.requestAnimationFrame(() => {
            celebrationCard.classList.add("celebration-card--visible");
        });

        window.setTimeout(() => {
            celebrationCard.classList.remove("celebration-card--visible");
            celebrationCard.classList.add("celebration-card--hide");
        }, 3600);

        window.setTimeout(() => {
            celebrationCard.remove();
        }, 4000);
    }

    if (celebrationContainer && !prefersReducedMotion) {
        const confettiColors = ["#d63384", "#6f42c1", "#ffd166", "#4dabf7", "#ffffff"];
        const partyEmoji = "🥳";
        const sparkleEmoji = ["✨", "🎉"];

        const addPiece = (classNames, configure) => {
            const piece = document.createElement("span");
            piece.className = classNames;
            configure(piece);
            celebrationContainer.appendChild(piece);
            return piece;
        };

        // Confetti raining from the top, across the full screen width
        for (let i = 0; i < 26; i += 1) {
            addPiece("confetti-piece confetti-top", (piece) => {
                piece.style.left = `${Math.random() * 100}vw`;
                piece.style.backgroundColor = confettiColors[Math.floor(Math.random() * confettiColors.length)];
                piece.style.animationDuration = `${1.8 + Math.random() * 1.2}s`;
                piece.style.animationDelay = `${Math.random() * 0.3}s`;
            });
        }

        // Confetti bursting in from the left edge
        for (let i = 0; i < 12; i += 1) {
            addPiece("confetti-piece confetti-left", (piece) => {
                piece.style.top = `${Math.random() * 100}vh`;
                piece.style.backgroundColor = confettiColors[Math.floor(Math.random() * confettiColors.length)];
                piece.style.setProperty("--burst-x", `${50 + Math.random() * 35}vw`);
                piece.style.setProperty("--burst-y", `${(Math.random() - 0.4) * 50}vh`);
                piece.style.animationDuration = `${1.6 + Math.random() * 1}s`;
                piece.style.animationDelay = `${Math.random() * 0.3}s`;
            });
        }

        // Confetti bursting in from the right edge
        for (let i = 0; i < 12; i += 1) {
            addPiece("confetti-piece confetti-right", (piece) => {
                piece.style.top = `${Math.random() * 100}vh`;
                piece.style.backgroundColor = confettiColors[Math.floor(Math.random() * confettiColors.length)];
                piece.style.setProperty("--burst-x", `${-(50 + Math.random() * 35)}vw`);
                piece.style.setProperty("--burst-y", `${(Math.random() - 0.4) * 50}vh`);
                piece.style.animationDuration = `${1.6 + Math.random() * 1}s`;
                piece.style.animationDelay = `${Math.random() * 0.3}s`;
            });
        }

        // A joyful confetti explosion shooting up from the bottom
        for (let i = 0; i < 20; i += 1) {
            addPiece("confetti-piece confetti-burst", (piece) => {
                piece.style.left = `${20 + Math.random() * 60}vw`;
                piece.style.backgroundColor = confettiColors[Math.floor(Math.random() * confettiColors.length)];
                piece.style.setProperty("--burst-x", `${(Math.random() - 0.5) * 70}vw`);
                piece.style.setProperty("--burst-y", `${-(45 + Math.random() * 30)}vh`);
                piece.style.animationDuration = `${1.4 + Math.random() * 0.8}s`;
                piece.style.animationDelay = `${Math.random() * 0.25}s`;
            });
        }

        // Large party-face emojis spread across distinct zones of the screen
        const emojiZones = [
            { top: "10%", left: "8%" }, { top: "14%", left: "50%" }, { top: "8%", left: "85%" },
            { top: "42%", left: "18%" }, { top: "40%", left: "78%" },
            { top: "72%", left: "12%" }, { top: "70%", left: "88%" },
        ];
        emojiZones.forEach((zone, index) => {
            addPiece("emoji-piece", (piece) => {
                piece.textContent = partyEmoji;
                piece.style.top = `calc(${zone.top} + ${(Math.random() - 0.5) * 6}vh)`;
                piece.style.left = `calc(${zone.left} + ${(Math.random() - 0.5) * 6}vw)`;
                piece.style.fontSize = `${2.2 + Math.random() * 1.4}rem`;
                piece.style.animationDuration = `${1.8 + Math.random() * 0.6}s`;
                piece.style.animationDelay = `${index * 0.08}s`;
            });
        });

        // Small twinkling sparkles (✨ and 🎉) scattered across the full screen
        for (let i = 0; i < 22; i += 1) {
            addPiece("sparkle-piece", (piece) => {
                piece.textContent = sparkleEmoji[Math.floor(Math.random() * sparkleEmoji.length)];
                piece.style.top = `${Math.random() * 100}vh`;
                piece.style.left = `${Math.random() * 100}vw`;
                piece.style.fontSize = `${0.9 + Math.random() * 0.7}rem`;
                piece.style.animationDuration = `${0.8 + Math.random() * 0.6}s`;
                piece.style.animationDelay = `${Math.random() * 1.2}s`;
            });
        }

        // Fast ~4-second splash, then everything is removed after it fades.
        window.setTimeout(() => {
            celebrationContainer.innerHTML = "";
        }, 4200);
    }
}
