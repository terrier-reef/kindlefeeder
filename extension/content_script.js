(function () {
  // Readability.js modifies the DOM — clone before passing
  function extractArticle() {
    const docClone = document.cloneNode(true);

    // BBC and some sites use Shadow DOM for article content.
    // Attempt to pierce the most common pattern: a single top-level shadow host
    // that contains the article body.
    function flattenShadowDom(root) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
      let node;
      while ((node = walker.nextNode())) {
        if (node.shadowRoot) {
          // Replace the shadow host's (cloned) counterpart with its shadow content
          try {
            const shadowContent = node.shadowRoot.cloneNode(true);
            node.appendChild(shadowContent);
          } catch (_) {}
        }
      }
    }

    try {
      flattenShadowDom(document.body);
    } catch (_) {}

    let article = null;

    try {
      article = new Readability(docClone).parse();
    } catch (_) {}

    // Fallback: if Readability found nothing (e.g. Shadow DOM blocked it),
    // grab the <article> element's innerHTML directly.
    if (!article || !article.textContent || article.textContent.trim().length < 200) {
      const articleEl = document.querySelector('article, [role="article"], main');
      if (articleEl) {
        article = {
          title: document.title,
          byline: null,
          content: articleEl.innerHTML,
          textContent: articleEl.innerText || articleEl.textContent,
        };
      }
    }

    if (!article) return null;

    return {
      title: article.title || document.title,
      author: article.byline || '',
      content: article.content,
    };
  }

  return extractArticle();
})();
