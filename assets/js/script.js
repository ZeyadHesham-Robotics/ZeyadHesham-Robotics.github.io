/* =====================================================================
   Zeyad Hesham — Portfolio Rendering Logic
   =====================================================================
   This file reads the constants defined in data.js and renders:
     - Core skills list
     - Category filters
     - Project cards (grid)
     - Project modal (opens on card click) with media gallery carousel
     - Hero stats and the copyright year

   You usually shouldn't need to edit this file - edit data.js instead
   to change content. Edit this if you want to change rendering behavior
   or add new interactive features.
   ===================================================================== */

function esc(s) {
    return String(s).replace(/[&<>"']/g, ch => ({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[ch]));
}

function pad(n, w = 2) { return String(n).padStart(w, '0'); }

/* ───── Skills render ───── */
(function renderSkills() {
    const grid = document.getElementById("skills-grid");
    SKILLS.forEach((s, i) => {
        const el = document.createElement("div");
        el.className = "skill-tag";
        el.innerHTML = `<span class="skill-index">${pad(i + 1)}</span>${esc(s)}`;
        grid.appendChild(el);
    });
    const header = document.querySelector(".section-header .section-caption");
    if (header) header.textContent = `[ ${pad(SKILLS.length)} disciplines ]`;
})();

/* ───── Filters render ───── */
(function renderFilters() {
    const bar = document.getElementById("filters");
    CATEGORIES.forEach((c, idx) => {
        const count = c.id === "all"
            ? PROJECTS.length
            : PROJECTS.filter(p => p.category === c.id).length;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "filter-btn" + (idx === 0 ? " active" : "");
        btn.dataset.filter = c.id;
        btn.innerHTML = `${esc(c.name)}<span class="filter-count">${count}</span>`;
        btn.addEventListener("click", () => {
            document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            renderProjects(c.id);
        });
        bar.appendChild(btn);
    });
})();

/* ───── Project cards ───── */
function renderProjects(filter = "all") {
    const grid = document.getElementById("projects-grid");
    grid.innerHTML = "";

    // Sort: featured first, then by year desc
    const filtered = (filter === "all" ? PROJECTS : PROJECTS.filter(p => p.category === filter))
        .slice()
        .sort((a, b) => {
            const fa = a.status === "featured" ? 0 : 1;
            const fb = b.status === "featured" ? 0 : 1;
            if (fa !== fb) return fa - fb;
            return (b.year || 0) - (a.year || 0);
        });

    document.getElementById("project-count").textContent =
        `[ ${pad(filtered.length)} project${filtered.length === 1 ? '' : 's'} ]`;

    if (filtered.length === 0) {
        grid.innerHTML = '<div class="empty-state">// no projects in this category</div>';
        return;
    }

    const frag = document.createDocumentFragment();

    filtered.forEach((project, idx) => {
        const statusInfo = statusConfig[project.status] || statusConfig.completed;
        const hasPhoto = !!project.image;

        const card = document.createElement("button");
        card.type = "button";
        card.className = "project-card";
        card.dataset.category = project.category;
        card.dataset.slug = project.slug;
        card.setAttribute("aria-label", `View details for ${project.title}`);

        const imageInner = hasPhoto
            ? `<img src="${esc(project.image)}" alt="${esc(project.title)}" loading="lazy" onerror="this.parentElement.classList.remove('has-photo'); this.remove();">`
            : `<div>${getCategoryEmoji(project.category)}</div>`;

        card.innerHTML = `
            <div class="project-image ${hasPhoto ? 'has-photo' : ''}">
                ${imageInner}
                <span class="project-id">PRJ_${pad(idx + 1)}</span>
                ${project.status === "featured"
                    ? `<span class="featured-star">★ FEATURED</span>`
                    : `<span class="project-year-badge">${esc(project.year)}</span>`}
            </div>
            <div class="project-content">
                <div class="project-meta-top">
                    <span class="tag tag-category">${esc(getCategoryName(project.category))}</span>
                    <span class="tag ${statusInfo.class}">${statusInfo.label}</span>
                    ${project.status === "featured"
                        ? `<span class="tag" style="background:transparent;color:var(--text-muted);border:1px solid var(--border);">${esc(project.year)}</span>`
                        : ''}
                </div>
                <h3 class="project-title">${esc(project.title)}</h3>
                <p class="project-description">${esc(project.description)}</p>
                <div class="project-tech">
                    ${project.techStack.slice(0, 5).map(t => `<span class="tech-tag">${esc(t)}</span>`).join("")}
                    ${project.techStack.length > 5 ? `<span class="tech-tag">+${project.techStack.length - 5}</span>` : ''}
                </div>
                <div class="project-footer">
                    <div class="project-links">
                        ${project.links && project.links.repository ? `<a href="${esc(project.links.repository)}" target="_blank" rel="noopener" class="project-link" data-stop>↗ repo</a>` : ''}
                        ${project.links && project.links.demo ? `<a href="${esc(project.links.demo)}" target="_blank" rel="noopener" class="project-link" data-stop>▶ demo</a>` : ''}
                    </div>
                    <span class="view-details">open →</span>
                </div>
            </div>
        `;

        card.addEventListener("click", () => openModal(project));
        frag.appendChild(card);
    });

    grid.appendChild(frag);

    grid.querySelectorAll("[data-stop]").forEach(a => {
        a.addEventListener("click", e => e.stopPropagation());
    });
}


/* ───── Modal (media gallery: images + video) ───── */
const backdrop              = document.getElementById("modal-backdrop");
const modalMedia            = document.getElementById("modal-media");
const modalMediaStage       = document.getElementById("modal-media-stage");
const modalMediaPrev        = document.getElementById("modal-media-prev");
const modalMediaNext        = document.getElementById("modal-media-next");
const modalMediaCounter     = document.getElementById("modal-media-counter");
const modalMediaDots        = document.getElementById("modal-media-dots");
const modalTitle            = document.getElementById("modal-title");
const modalMeta             = document.getElementById("modal-meta");
const modalDescription      = document.getElementById("modal-description");
const modalDetailWrap       = document.getElementById("modal-detail-wrap");
const modalAchWrap          = document.getElementById("modal-achievements-wrap");
const modalAch              = document.getElementById("modal-achievements");
const modalTech             = document.getElementById("modal-tech");
const modalLinks            = document.getElementById("modal-links");
const modalClose            = document.getElementById("modal-close");
const modalBreadcrumbCategory = document.getElementById("modal-breadcrumb-category");

let lastFocused         = null;
let currentGallery      = [];
let currentGalleryIndex = 0;

/* Derive the gallery array for a project, with backward-compat fallback. */
function deriveGallery(project) {
    if (Array.isArray(project.gallery) && project.gallery.length > 0) {
        return project.gallery.filter(m => m && m.src && (m.type === "image" || m.type === "video"));
    }
    if (project.image) {
        return [{ type: "image", src: project.image, caption: project.title }];
    }
    return [];
}

function stopAllVideos() {
    modalMediaStage.querySelectorAll("video").forEach(v => {
        try { v.pause(); v.currentTime = 0; } catch (_) { /* ignore */ }
    });
}

/* Render a single media item (image or video) into the stage. */
function renderMediaItem(item, project) {
    stopAllVideos();
    modalMediaStage.innerHTML = "";

    if (!item) {
        modalMedia.classList.remove("has-media");
        const span = document.createElement("span");
        span.className = "modal-media-emoji";
        span.textContent = getCategoryEmoji(project.category);
        modalMediaStage.appendChild(span);
        return;
    }

    modalMedia.classList.add("has-media");

    if (item.type === "image") {
        const img = document.createElement("img");
        img.src = item.src;
        img.alt = item.caption || project.title;
        img.loading = "lazy";
        img.onerror = () => {
            modalMedia.classList.remove("has-media");
            modalMediaStage.innerHTML = "";
            const span = document.createElement("span");
            span.className = "modal-media-emoji";
            span.textContent = getCategoryEmoji(project.category);
            modalMediaStage.appendChild(span);
        };
        modalMediaStage.appendChild(img);
    } else if (item.type === "video") {
        const video = document.createElement("video");
        video.src = item.src;
        video.controls = true;
        video.playsInline = true;
        video.preload = "metadata";
        if (item.poster) video.poster = item.poster;
        video.onerror = () => {
            modalMedia.classList.remove("has-media");
            modalMediaStage.innerHTML = "";
            const span = document.createElement("span");
            span.className = "modal-media-emoji";
            span.textContent = getCategoryEmoji(project.category);
            modalMediaStage.appendChild(span);
        };
        modalMediaStage.appendChild(video);
    }

    if (item.caption) {
        const cap = document.createElement("div");
        cap.className = "modal-media-caption";
        cap.textContent = item.caption;
        modalMediaStage.appendChild(cap);
    }
}

function updateGalleryUI(project) {
    const total = currentGallery.length;
    const multi = total > 1;

    modalMediaPrev.hidden    = !multi;
    modalMediaNext.hidden    = !multi;
    modalMediaCounter.hidden = !multi;
    modalMediaDots.hidden    = !multi;

    if (multi) {
        modalMediaCounter.textContent = pad(currentGalleryIndex + 1) + " / " + pad(total);
        modalMediaDots.innerHTML = "";
        currentGallery.forEach((_, i) => {
            const dot = document.createElement("button");
            dot.type = "button";
            dot.className = "modal-media-dot" + (i === currentGalleryIndex ? " active" : "");
            dot.setAttribute("role", "tab");
            dot.setAttribute("aria-selected", i === currentGalleryIndex ? "true" : "false");
            dot.setAttribute("aria-label", "Go to media " + (i + 1));
            dot.addEventListener("click", () => {
                currentGalleryIndex = i;
                renderMediaItem(currentGallery[i], project);
                updateGalleryUI(project);
            });
            modalMediaDots.appendChild(dot);
        });
    }
}

function goToGalleryIndex(i, project) {
    if (!currentGallery.length) return;
    const total = currentGallery.length;
    currentGalleryIndex = ((i % total) + total) % total;
    renderMediaItem(currentGallery[currentGalleryIndex], project);
    updateGalleryUI(project);
}

function openModal(project) {
    const statusInfo = statusConfig[project.status] || statusConfig.completed;

    currentGallery = deriveGallery(project);
    currentGalleryIndex = 0;
    if (currentGallery.length === 0) {
        renderMediaItem(null, project);
    } else {
        renderMediaItem(currentGallery[0], project);
    }
    updateGalleryUI(project);

    modalMediaPrev.onclick = () => goToGalleryIndex(currentGalleryIndex - 1, project);
    modalMediaNext.onclick = () => goToGalleryIndex(currentGalleryIndex + 1, project);

    modalTitle.textContent = project.title;
    modalDescription.textContent = project.description;
    modalBreadcrumbCategory.textContent = getCategoryName(project.category).toLowerCase();

    modalMeta.innerHTML =
        '<span class="tag tag-category">' + esc(getCategoryName(project.category)) + '</span>' +
        '<span class="tag ' + statusInfo.class + '">' + statusInfo.label + '</span>' +
        '<span class="tag" style="background:transparent;color:var(--text-muted);border:1px solid var(--border);">' + esc(project.year) + '</span>' +
        '<span class="tag" style="background:transparent;color:var(--text-dim);border:1px solid var(--border);">' + esc(project.slug) + '</span>';

    if (project.detail) {
        modalDetailWrap.textContent = project.detail;
        modalDetailWrap.hidden = false;
    } else {
        modalDetailWrap.hidden = true;
    }

    if (project.achievements && project.achievements.length) {
        modalAch.innerHTML = project.achievements.map(a => "<li>" + esc(a) + "</li>").join("");
        modalAchWrap.hidden = false;
    } else {
        modalAchWrap.hidden = true;
    }

    modalTech.innerHTML = project.techStack.map(t => '<span class="tech-tag">' + esc(t) + '</span>').join("");

    const repo = project.links && project.links.repository;
    const demo = project.links && project.links.demo;
    const docs = project.links && project.links.documentation;

    if (repo || demo || docs) {
        modalLinks.className = "modal-links";
        modalLinks.innerHTML =
            (repo ? '<a href="' + esc(repo) + '" target="_blank" rel="noopener" class="btn btn-primary">\u2197 Repository</a>' : "") +
            (demo ? '<a href="' + esc(demo) + '" target="_blank" rel="noopener" class="btn btn-ghost">\u25B6 Demo</a>' : "") +
            (docs ? '<a href="' + esc(docs) + '" target="_blank" rel="noopener" class="btn btn-ghost">\uD83D\uDCC4 Docs</a>' : "");
    } else {
        modalLinks.className = "modal-links-empty";
        modalLinks.innerHTML = "// no public links available yet";
    }

    lastFocused = document.activeElement;
    backdrop.classList.add("open");
    backdrop.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    setTimeout(() => modalClose.focus(), 50);
}

function closeModal() {
    stopAllVideos();
    backdrop.classList.remove("open");
    backdrop.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus();
}

modalClose.addEventListener("click", closeModal);
backdrop.addEventListener("click", e => { if (e.target === backdrop) closeModal(); });
document.addEventListener("keydown", e => {
    if (!backdrop.classList.contains("open")) return;
    if (e.key === "Escape") closeModal();
    else if (e.key === "ArrowLeft"  && currentGallery.length > 1) modalMediaPrev.click();
    else if (e.key === "ArrowRight" && currentGallery.length > 1) modalMediaNext.click();
});

/* Touch swipe (mobile) for the media gallery */
let touchStartX = null;
modalMediaStage.addEventListener("touchstart", e => {
    if (e.touches.length === 1) touchStartX = e.touches[0].clientX;
}, { passive: true });
modalMediaStage.addEventListener("touchend", e => {
    if (touchStartX === null || currentGallery.length < 2) { touchStartX = null; return; }
    const endX = e.changedTouches[0] ? e.changedTouches[0].clientX : touchStartX;
    const dx = endX - touchStartX;
    if (Math.abs(dx) > 40) {
        if (dx < 0) modalMediaNext.click();
        else        modalMediaPrev.click();
    }
    touchStartX = null;
}, { passive: true });

/* ───── Stats ───── */
document.getElementById("stat-projects").textContent = pad(PROJECTS.length);
document.getElementById("stat-categories").textContent = pad(new Set(PROJECTS.map(p => p.category)).size);
document.getElementById("copyright-year").textContent = new Date().getFullYear();

/* Initial render */
renderProjects();
