import os

os.environ["DEBUG"] = "false"

from src.infra.tool.reveal_project_tool import detect_template


def test_detect_template_prefers_package_json_dependencies():
    package_json = """
    {
      "dependencies": {
        "react": "^19.0.0"
      }
    }
    """

    result = detect_template(package_json, {"/index.html", "/app.js"})

    assert result == "react"


def test_detect_template_falls_back_to_react_entry_files():
    result = detect_template(
        "{}",
        {
            "/index.html",
            "/src/main.jsx",
            "/src/App.jsx",
        },
    )

    assert result == "react"


def test_detect_template_falls_back_to_vue_entry_files():
    result = detect_template(
        "{}",
        {
            "/index.html",
            "/src/main.js",
            "/src/App.vue",
        },
    )

    assert result == "vue"


def test_detect_template_returns_static_for_plain_html_projects():
    result = detect_template(
        "{}",
        {
            "/index.html",
            "/styles.css",
            "/app.js",
        },
    )

    assert result == "static"


def test_detect_template_falls_back_to_react_without_package_or_index_html():
    result = detect_template(
        "",
        {
            "/src/main.jsx",
            "/src/App.jsx",
        },
    )

    assert result == "react"


def test_detect_template_supports_svelte_from_package_json():
    package_json = """
    {
      "dependencies": {
        "svelte": "^5.0.0"
      }
    }
    """

    result = detect_template(package_json, {"/src/App.svelte", "/src/main.js"})

    assert result == "svelte"


def test_detect_template_supports_solid_from_package_json():
    package_json = """
    {
      "dependencies": {
        "solid-js": "^1.9.0"
      }
    }
    """

    result = detect_template(package_json, {"/src/index.tsx", "/src/App.tsx"})

    assert result == "solid"


def test_detect_template_supports_nextjs_from_package_json():
    package_json = """
    {
      "dependencies": {
        "next": "^15.0.0"
      }
    }
    """

    result = detect_template(package_json, {"/app/page.tsx", "/app/layout.tsx"})

    assert result == "nextjs"


def test_detect_template_supports_angular_from_package_json():
    package_json = """
    {
      "dependencies": {
        "@angular/core": "^19.0.0"
      }
    }
    """

    result = detect_template(package_json, {"/angular.json", "/src/main.ts"})

    assert result == "angular"


def test_detect_template_falls_back_to_svelte_entry_files():
    result = detect_template(
        "{}",
        {
            "/src/App.svelte",
            "/src/main.js",
        },
    )

    assert result == "svelte"


def test_detect_template_falls_back_to_nextjs_pages_router_files():
    result = detect_template(
        "{}",
        {
            "/pages/index.tsx",
            "/pages/_app.tsx",
        },
    )

    assert result == "nextjs"


def test_detect_template_falls_back_to_angular_project_files():
    result = detect_template(
        "{}",
        {
            "/angular.json",
            "/src/main.ts",
        },
    )

    assert result == "angular"
