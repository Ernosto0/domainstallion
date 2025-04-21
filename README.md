<div id="top">

<!-- HEADER STYLE: MODERN -->
<div align="center" style="position: relative; width: 100%; height: 100%;">


# Domainstallion

<em>AI-powered platform to generate, score, and monitor domain names with real-time registrar and social media checking.</em>

<div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 8px; margin: 20px 0;">
<img src="https://img.shields.io/badge/FastAPI-009688.svg?style=flat-square&logo=FastAPI&logoColor=white" alt="FastAPI">
<img src="https://img.shields.io/badge/Python-3776AB.svg?style=flat-square&logo=Python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/SQLAlchemy-D71F00.svg?style=flat-square&logo=SQLAlchemy&logoColor=white" alt="SQLAlchemy">
<img src="https://img.shields.io/badge/AIOHTTP-2C5BB4.svg?style=flat-square&logo=AIOHTTP&logoColor=white" alt="AIOHTTP">
<img src="https://img.shields.io/badge/OpenAI-412991.svg?style=flat-square&logo=OpenAI&logoColor=white" alt="OpenAI">
<img src="https://img.shields.io/badge/Pydantic-E92063.svg?style=flat-square&logo=Pydantic&logoColor=white" alt="Pydantic">
<img src="https://img.shields.io/badge/Jinja2-B41717.svg?style=flat-square&logo=Jinja&logoColor=white" alt="Jinja2">
<img src="https://img.shields.io/badge/Bootstrap-7952B3.svg?style=flat-square&logo=Bootstrap&logoColor=white" alt="Bootstrap">
</div>
</div>
</div>
<br>

---

## 💻 Technical Showcase

As a full-stack developer, I built Domain Creator to demonstrate my expertise in modern web development. This project showcases my ability to architect and implement complex systems with multiple integrated services.

### 🔧 Key Technical Skills Demonstrated

| Expertise | Implementation Details |
|:----------|:----------------------|
| **Asynchronous Programming** | Implemented with Python's `asyncio` for non-blocking I/O, handling concurrent API requests efficiently. Used `aiohttp` for asynchronous HTTP requests with connection pooling. |
| **API Integration** | Integrated with multiple external APIs (domain registrars, social media platforms, USPTO trademark database) with proper error handling and rate limiting. |
| **AI-Powered Generation** | Leveraged OpenAI's API for intelligent brand name generation with domain-specific prompting and context handling. |
| **Authentication System** | Built a complete auth system with JWT tokens, password hashing, and OAuth 2.0 integration (Google) for secure user accounts. |
| **Database Design** | Implemented SQLAlchemy ORM with properly normalized tables, relationships, and efficient queries. |
| **RESTful API Design** | Created a comprehensive FastAPI backend with proper validation, error handling, and documentation. |
| **Caching Strategies** | Implemented intelligent caching of external API responses to improve performance and reduce costs. |
| **Rate Limiting** | Built a custom rate limiter to prevent abuse and manage API quotas effectively. |
| **Template Rendering** | Used Jinja2 templating engine for server-side rendering with custom filters and template inheritance. |
| **Responsive Frontend** | Created a mobile-first responsive design with custom CSS and Bootstrap components. |

---

## 🚀 Feature Showcase

### 🔍 Intelligent Brand Name Generation
The system uses OpenAI's language models to generate contextually relevant and creative brand names based on user keywords and parameters. It implements sophisticated filtering to ensure quality results.

```python
# Snippet from brand name generation
async def generate_names(self, keywords, style="neutral", num_suggestions=20):
    # Generate creative and contextually relevant brand names using OpenAI
    # with custom prompting based on selected style
```

### 📊 Multi-Factor Scoring
Each is evaluated using a sophisticated scoring algorithm that analyzes:
- Length optimization
- Dictionary word recognition
- Pronunciation analysis
- Letter pattern evaluation
- TLD value assessment

```python
# scoring system
def calculate_total_score(self, domain_name: str, tld: str) -> Dict[str, Any]:
    # Calculate weighted scores for quality factors
    total_score = (
        length_score["score"] * 0.2
        + dictionary_score["score"] * 0.2
        + pronounce_score["score"] * 0.2
        + repetition_score["score"] * 0.2
        + tld_score["score"] * 0.2
    )
```

The scoring system includes:

#### 1. Length Optimization (20%)
Evaluates the optimal length for memorability and usability:
- 6-10 characters: Ideal length (100%)
- 4-5 or 11-12 characters: Good length (80%)
- 3 or 13-15 characters: Acceptable length (60%)
- 16+ characters: Too long (40%)

#### 2. Dictionary Word Recognition (20%)
Analyzes how the relates to common words:
- Exact dictionary word or creative blend: Highest score (100%)
- Partial word match or recognizable pattern: Medium score (70%)
- Random characters: Lowest score (30%)

#### 3. Pronunciation Assessment (20%)
Measures how easily the can be pronounced:
- Clear vowel-consonant patterns: High score (90-100%)
- Pronounceable but complex: Medium score (60-80%)
- Difficult pronunciation: Low score (30-50%)

#### 4. Repetition & Pattern Analysis (20%)
Identifies undesirable repetition or patterns:
- No repeating characters: High score (100%)
- Minimal repetition: Medium score (70%)
- Excessive repetition: Low score (40%)

#### 5. TLD Evaluation (20%)
Assesses the value and perception of different TLDs:
- .com: Premium TLD (100%)
- .io, .ai, .app: Industry-specific premium TLDs (90%)
- .net, .org: Standard alternatives (80%)
- .info, .biz: Less desirable options (60%)

The visual representation of these scores provides users with a comprehensive understanding of each domain's strengths and weaknesses.

### 🌐 Multi-Provider Checking
The system checks availability across multiple registrars simultaneously, comparing pricing and availability in real-time.
- GoDaddy.com
- Dynadot.com
- Namesilo.com
- Porkbun.com

### 📱 Social Media Username Verification
Integrated social media platform checking to help users find consistent branding across domains and social platforms.

```python
# Social media availability checking across platforms
async def check_social_media(username: str) -> Dict:
    # Clean the username and check availability across
    # Twitter, YouTube, Reddit, and other platforms
```


### 👁️ Watchlist System
Users can monitor unavailable domains with automatic e-mail notifications via Mailersend API when they become available.

```python
# Background task to check watchlist domains
async def check_watchlist_domains():
    # Periodically checks if watched domains become available
    # and sends alerts to users who enabled notifications
```

---

## 🛠️ Architecture Highlights

### Backend Architecture
- **FastAPI** for high-performance asynchronous API endpoints
- **SQLAlchemy ORM** for database interactions with proper relationship modeling
- **Pydantic** for data validation and serialization
- **Background Tasks** for watchlist monitoring and cache management
- **Jinja2 Templates** for server-side rendering with a clean separation of concerns
- **Environment-aware Configuration** for seamless development and production deployments

### Security Implementation
- **JWT Authentication** with proper token expiration and refresh
- **Password Hashing** using industry-standard algorithms
- **CORS Configuration** with proper security settings
- **Rate Limiting** to prevent abuse and API overuse

```python
# Rate limiting implementation
@app.get("/check-social-media/{username}")
@rate_limit(calls=20, period=3600)  # 20 requests per hour
async def check_social_media_endpoint(request: Request, username: str):
    # Social media availability checking with rate limiting
```

### Frontend Integration
- **Custom CSS Framework**: Implemented a comprehensive custom CSS system with modern glass morphism, variable-based theming, and detailed animations
- **Advanced JavaScript Implementation**: Built a complete frontend application with vanilla JavaScript using modern ES6+ features
- **Dynamic DOM Manipulation**: Created sophisticated DOM generation and manipulation for dynamic content updates without frontend frameworks
- **Custom Animation System**: Designed loading sequences and micro-interactions using CSS transitions and JavaScript timing
- **Responsive Design**: Implemented a mobile-first approach with custom media queries and adaptive layouts
- **Jinja2 Template Engine**: Leveraged Jinja2's powerful template inheritance, custom filters, and macros to create modular and maintainable frontend code
- **Bootstrap Integration**: Enhanced UI with customized Bootstrap components while maintaining a unique visual identity
- **Cookie Management**: Created custom cookie consent and management system for GDPR compliance

### 🎨 CSS Styling System

The application uses a sophisticated CSS system with custom variables and modern styling techniques:

```css
/* CSS Variables for theme management */
:root {
    --primary-color: #4361ee;
    --primary-light: rgba(67, 97, 238, 0.1);
    --secondary-color: #3a0ca3;
    --accent-color: #f72585;
    --success-color: #4cc9f0;
    --warning-color: #f8961e;
    --danger-color: #f94144;
    --border-radius: 12px;
    --box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    --transition: all 0.25s ease-in-out;
    --gradient-primary: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    --glass-bg: rgba(255, 255, 255, 0.95);
    --glass-border: rgba(255, 255, 255, 0.2);
    --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}
```

Key features of the styling system:
- **Glass Morphism**: Modern UI with backdrop filters and transparency effects
- **CSS Variables**: Comprehensive theming system with reusable variables
- **Animation System**: Custom keyframe animations and transitions for UI elements
- **Responsive Grid**: Custom grid system with breakpoints for all device sizes
- **Interactive Elements**: Hover and focus states with smooth transitions
- **Accessibility**: High-contrast UI elements with proper focus states
- **Custom Components**: Specialized styling for cards, score indicators, and form elements

### 🖥️ Interactive Features

- **Real-time Checking**: Multi-provider availability checking with provider selection and price comparison
- **Social Media Username Verification**: Integrated UI for checking username availability across Twitter, YouTube, and Reddit
- **Advanced Form Interface**: Implemented range sliders, toggles, and other custom form controls with real-time feedback
- **Interactive Results Display**: Created expandable/collapsible sections with sorting and filtering capabilities
- **User Authentication Flow**: Smooth login/registration modal system with saved state management and OAuth integration
- **Toast Notification System**: Custom toast notifications with auto-dismissal and context-aware styling
- **Favorites & Watchlist Management**: Full CRUD operations for saved domains with UI transitions and error handling
- **Advanced Loading Interface**: Multi-step loading visualization with progress indicators that adjust based on actual API response times

### 🎨 Template Rendering System

The application uses a sophisticated template rendering system with Jinja2:

```html
<!-- Template inheritance example -->
{% extends "base.html" %}

{% block content %}
<div class="container about-page">
    <!-- Page-specific content here -->
</div>
{% endblock %}
```

Key features of the templating system:
- **Template Inheritance**: Base templates with extendable blocks for consistent layouts
- **Custom Filters**: HTTPS URL filter for secure resource loading
- **Context Processing**: Dynamic template context based on authentication state
- **Response Headers**: Proper content security policy headers for template responses
- **Error Handling**: Custom error templates with helpful debugging information in development

### 🍪 Cookie Consent System

The application implements a GDPR-compliant cookie consent system:

```javascript
// Simple cookie consent implementation
(function() {
    // Function to check if cookie is set
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }
    
    // Function to set cookie
    function setCookie(name, value, days) {
        let expires = "";
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "") + expires + "; path=/";
    }
    
    // Show banner if consent not given
    if (!getCookie('cookieConsent')) {
        const banner = document.getElementById('cookie-consent-banner');
        if (banner) banner.style.display = 'block';
    }
})();
```

Features of the cookie system:
- **Unobtrusive Banner**: Glass-morphism styled cookie consent banner
- **Persistent Settings**: Year-long cookie persistence for user preferences
- **Privacy Integration**: Direct links to privacy policy for compliance
- **Responsive Design**: Mobile-optimized banner layout
- **Accessibility**: ARIA-compliant cookie consent implementation

---

## 👨‍💻 Development Approach

This project demonstrates my approach to software development:

1. **Modular Architecture**: Separated concerns with dedicated service modules for each major function
2. **Error Handling**: Comprehensive error handling and user feedback throughout the codebase
3. **Performance Optimization**: Efficient caching and concurrency for external API calls
4. **Documentation**: Clear, comprehensive code documentation
5. **Testing**: Structured for testability with dependency injection patterns

---

<div align="center">

## 🔗 Connect With Me

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)]([https://www.linkedin.com](https://www.linkedin.com/in/cinar-aksoy-5023a1240/))
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)]([https://github.com](https://github.com/Ernosto0))

</div>

<div align="right">

[![][back-to-top]](#top)

</div>


[back-to-top]: https://img.shields.io/badge/-BACK_TO_TOP-151515?style=flat-square
