/**
 * categoryHelp.js
 *
 * Help content for each issue category in TalkingToad.
 * Provides context about what each category means and why it matters.
 *
 * Each entry has:
 *   - title:       Short category name
 *   - description: What this category covers
 *   - why:         Why this category matters for nonprofits
 *   - common:      Common issues in this category
 */

export const categoryHelp = {
  broken_link: {
    title: "Broken Links",
    description:
      "Broken links are hyperlinks on your site that point to pages or resources that can't be loaded. " +
      "This includes internal links (to other pages on your site) and external links (to other websites).",
    why:
      "Broken links frustrate visitors and damage trust. When someone clicks a link expecting helpful " +
      "information and gets an error page instead, they're likely to leave your site. Search engines " +
      "also see broken links as a sign of poor site maintenance, which can hurt your rankings.",
    common: [
      "404 errors (page not found)",
      "Deleted pages",
      "Typos in URLs",
      "External sites that have moved or shut down",
      "HTTP timeout or connection errors"
    ]
  },

  metadata: {
    title: "Metadata",
    description:
      "Metadata is information about your pages that helps search engines and social media platforms " +
      "understand and display your content. This includes page titles, meta descriptions, Open Graph tags, " +
      "and canonical URLs.",
    why:
      "Good metadata is your first impression in search results and social media shares. It's what people " +
      "see before they click through to your site. Clear, compelling metadata improves click-through rates " +
      "from Google and helps people find the specific services or information they're looking for.",
    common: [
      "Missing or duplicate page titles",
      "Titles that are too short or too long",
      "Missing meta descriptions",
      "Descriptions that don't match page content",
      "Missing social sharing tags"
    ]
  },

  heading: {
    title: "Headings",
    description:
      "Headings (H1, H2, H3, etc.) provide structure to your content, like a table of contents. " +
      "They help both people and search engines understand the organization and hierarchy of information " +
      "on each page.",
    why:
      "Screen readers use headings to navigate pages, so proper heading structure is essential for " +
      "accessibility. Search engines also use headings to understand what your content is about. " +
      "A clear heading hierarchy helps visitors skim your content and find what they need quickly.",
    common: [
      "Missing H1 (main page heading)",
      "Multiple H1 tags on one page",
      "Skipping heading levels (H1 → H3)",
      "Headings out of logical order",
      "Using headings for visual styling instead of structure"
    ]
  },

  redirect: {
    title: "Redirects",
    description:
      "Redirects automatically send visitors from one URL to another. This happens when pages move or " +
      "are deleted. Common types include 301 (permanent) and 302 (temporary) redirects.",
    why:
      "Too many redirects slow down your site and create a poor user experience. Each redirect adds " +
      "loading time, and redirect chains (A → B → C) are especially problematic. Search engines also " +
      "prefer direct links over redirect chains.",
    common: [
      "Redirect chains (multiple hops)",
      "Redirect loops (A → B → A)",
      "HTTP → HTTPS redirect issues",
      "www vs non-www redirects",
      "Using temporary (302) instead of permanent (301) redirects"
    ]
  },

  crawlability: {
    title: "Crawlability",
    description:
      "Crawlability is how easily search engines can discover and access all the pages on your site. " +
      "Issues in this category prevent search engines from properly indexing your content.",
    why:
      "If search engines can't crawl your pages, those pages won't appear in search results — no matter " +
      "how good the content is. For nonprofits trying to reach people who need their services, being " +
      "invisible in search is a critical problem.",
    common: [
      "robots.txt blocking important pages",
      "noindex tags preventing indexing",
      "Missing or orphaned pages",
      "Pagination issues",
      "AJAX content not accessible to crawlers"
    ]
  },

  duplicate: {
    title: "Duplicates",
    description:
      "Duplicate content issues occur when the same (or very similar) content appears at multiple URLs " +
      "on your site. This can confuse search engines about which version to show in results.",
    why:
      "When search engines find duplicate content, they have to choose which version to rank. Often, " +
      "none of the duplicates rank as well as a single unique page would. This dilutes your search " +
      "presence and can make it harder for people to find your most important pages.",
    common: [
      "Same content on multiple URLs",
      "Print versions of pages",
      "Session IDs in URLs creating duplicates",
      "www vs non-www versions",
      "HTTP vs HTTPS versions",
      "Tag and category pages with duplicate content"
    ]
  },

  sitemap: {
    title: "Sitemap",
    description:
      "A sitemap is an XML file that lists all the important pages on your website, helping search engines " +
      "discover and index your content. It's like a roadmap of your site structure.",
    why:
      "Sitemaps help search engines find all your pages, especially new content or pages that aren't " +
      "well-linked from other parts of your site. For nonprofits with event calendars, resource pages, " +
      "or frequently updated content, a good sitemap ensures everything gets indexed quickly.",
    common: [
      "Missing sitemap entirely",
      "Sitemap not submitted to Google Search Console",
      "Sitemap includes noindex pages",
      "Outdated URLs in sitemap",
      "Sitemap over the 50MB size limit",
      "Incorrect sitemap formatting"
    ]
  },

  security: {
    title: "Security",
    description:
      "Security issues include missing HTTPS encryption, mixed content (HTTP resources on HTTPS pages), " +
      "and other vulnerabilities that could put your visitors or site at risk.",
    why:
      "Security matters for trust and safety. Modern browsers show 'Not Secure' warnings for non-HTTPS " +
      "sites, which can scare visitors away. For nonprofits handling donations, contact forms, or any " +
      "personal information, HTTPS is essential. Google also ranks HTTPS sites higher than HTTP sites.",
    common: [
      "Site not using HTTPS",
      "Mixed content (HTTP images/scripts on HTTPS pages)",
      "Invalid SSL certificates",
      "Missing security headers (HSTS)",
      "Unsafe cross-origin resources"
    ]
  },

  url_structure: {
    title: "URL Structure",
    description:
      "URL structure issues include overly long URLs, special characters, or confusing URL patterns " +
      "that make it hard for people and search engines to understand what a page is about.",
    why:
      "Clean, descriptive URLs are easier to share, remember, and understand. They also help search " +
      "engines understand your content. A URL like 'yoursite.org/counselling-services' is much better " +
      "than 'yoursite.org/page?id=12345' — both for SEO and for people trying to navigate your site.",
    common: [
      "URLs over 100 characters",
      "Special characters in URLs",
      "Too many parameters (?id=1&cat=2)",
      "Non-descriptive URLs (page-1, post-123)",
      "Inconsistent URL patterns"
    ]
  },

  image: {
    title: "Images",
    description:
      "Image issues cover accessibility (missing alt text), performance (oversized files), and technical " +
      "problems (broken images, poor compression). Images are a major part of modern websites but often " +
      "overlooked for optimization. TalkingToad provides AI-powered image analysis to evaluate and improve your images.",
    why:
      "Images without alt text are invisible to screen readers, excluding people with visual impairments. " +
      "Oversized images slow down your site significantly — a major problem when people are on mobile " +
      "networks. Fast-loading, accessible images improve both user experience and search rankings.",
    common: [
      "Missing alt text descriptions",
      "Alt text that just says 'image' or repeats the filename",
      "Images over 200KB",
      "Using JPEG/PNG instead of modern formats (WebP)",
      "Serving full-size images when smaller versions would work",
      "Broken image links"
    ],
    aiScores: {
      title: "AI Image Analysis Scores",
      description: "When you use 'AI Analyze', three scores are calculated:",
      scores: [
        {
          name: "Accuracy Score (0-100)",
          description: "How well your current alt text describes what's actually in the image. A score of 100 means perfect accuracy, while 0 means the alt text is missing or completely wrong."
        },
        {
          name: "Quality Score (0-100)",
          description: "How good your alt text is for SEO and accessibility. Considers appropriate length, relevant keywords, natural language, and context. Generic alt text like 'image' or 'photo' scores low."
        },
        {
          name: "Semantic Score (0-100)",
          description: "The average of Accuracy and Quality scores. This overall score affects your image's total score and represents the semantic value for both users and search engines."
        }
      ],
      howItWorks: "The AI vision model sees the actual image content, compares it to your current alt text, scores both accuracy and quality, then suggests improved alt text based on what it sees."
    }
  },

  ai_readiness: {
    title: "AI Readiness",
    description:
      "AI Readiness measures how well your site is prepared for AI tools like ChatGPT, Google Gemini, " +
      "and Perplexity. This includes having an /llms.txt file, clear site structure, and semantic HTML " +
      "that helps AI understand your content.",
    why:
      "More people are using AI chatbots to find services and information. If your site isn't AI-ready, " +
      "you won't be recommended when someone asks 'What mental health services are available in Vancouver?' " +
      "Being discoverable by AI is becoming as important as being discoverable by Google.",
    common: [
      "Missing /llms.txt file",
      "Poor semantic HTML structure",
      "Content not optimized for natural language queries",
      "Missing schema markup",
      "Unclear content hierarchy"
    ]
  }
}

/**
 * Get help content for a specific category
 */
export function getCategoryHelp(categoryKey) {
  return categoryHelp[categoryKey] || null
}

/**
 * Get all category help entries
 */
export function getAllCategoryHelp() {
  return categoryHelp
}
