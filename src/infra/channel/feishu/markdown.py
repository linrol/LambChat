"""
Feishu Markdown adapter for converting standard Markdown to lark_md format.

飞书 lark_md 支持的语法:
- **粗体** / *斜体*
- `行内代码`
- [链接](url)
- 引用块 (> )
- 有序/无序列表

不支持:
- ```代码块``` (需要用其他方式处理)
- 标题 (#) (需要转换为粗体)
- 表格

注意：飞书 lark_md 中的引用块 (> ) 内部不能嵌套其他格式（如 `code`），
否则会导致渲染异常。
"""

import re


class FeishuMarkdownAdapter:
    """将标准 Markdown 转换为飞书 lark_md 兼容格式"""

    # 代码块占位符
    CODE_BLOCK_PLACEHOLDER = "\u0000CODE_BLOCK_{}\u0000"
    INLINE_CODE_PLACEHOLDER = "\u0000INLINE_CODE_{}\u0000"

    @classmethod
    def adapt(cls, text: str) -> str:
        """将 markdown 文本适配为飞书 lark_md 格式"""
        if not text:
            return text

        # 1. 保护代码块（先处理，避免被其他规则干扰）
        text, code_blocks = cls._extract_code_blocks(text)

        # 2. 保护行内代码
        text, inline_codes = cls._extract_inline_codes(text)

        # 3. 转换标题为粗体格式
        text = cls._convert_headers(text)

        # 4. 处理列表（确保正确的缩进和换行）
        text = cls._fix_lists(text)

        # 5. 处理引用块
        text = cls._fix_blockquotes(text)

        # 6. 优化段落间距
        text = cls._fix_paragraphs(text)

        # 7. 恢复行内代码
        text = cls._restore_inline_codes(text, inline_codes)

        # 8. 恢复代码块（转换为纯文本块，避免嵌套格式问题）
        text = cls._restore_code_blocks(text, code_blocks)

        return text.strip()

    @classmethod
    def _extract_code_blocks(cls, text: str) -> tuple[str, dict]:
        """提取代码块，用占位符替换"""
        code_blocks = {}
        counter = [0]

        def replace_block(match: re.Match) -> str:
            lang = match.group(1) or ""
            code = match.group(2)
            idx = counter[0]
            counter[0] += 1
            code_blocks[idx] = (lang, code)
            return cls.CODE_BLOCK_PLACEHOLDER.format(idx)

        # 匹配 ```lang\ncode\n``` 格式
        pattern = r"```(\w*)\n(.*?)```"
        text = re.sub(pattern, replace_block, text, flags=re.DOTALL)

        return text, code_blocks

    @classmethod
    def _extract_inline_codes(cls, text: str) -> tuple[str, dict]:
        """提取行内代码，用占位符替换"""
        inline_codes = {}
        counter = [0]

        def replace_code(match: re.Match) -> str:
            code = match.group(1)
            idx = counter[0]
            counter[0] += 1
            inline_codes[idx] = code
            return cls.INLINE_CODE_PLACEHOLDER.format(idx)

        # 匹配 `code` 格式（非贪婪）
        text = re.sub(r"`([^`]+)`", replace_code, text)

        return text, inline_codes

    @classmethod
    def _convert_headers(cls, text: str) -> str:
        """将 markdown 标题转换为飞书兼容格式"""
        lines = text.split("\n")
        result = []

        for line in lines:
            # 匹配 # 标题格式
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                content = header_match.group(2)
                # 转换为粗体 + 换行
                result.append(f"**{content}**")
                result.append("")  # 空行分隔
            else:
                result.append(line)

        return "\n".join(result)

    @classmethod
    def _fix_lists(cls, text: str) -> str:
        """修复列表格式"""
        lines = text.split("\n")
        result: list[str] = []
        in_list = False

        for line in lines:
            # 检测列表项
            is_list_item = bool(re.match(r"^(\s*)[-*+]\s+", line)) or bool(
                re.match(r"^(\s*)\d+\.\s+", line)
            )

            if is_list_item:
                # 确保列表项前有换行（如果不是连续列表）
                if not in_list and result and result[-1].strip():
                    result.append("")
                in_list = True
            else:
                if in_list and line.strip():
                    # 列表结束，添加空行
                    result.append("")
                in_list = False

            result.append(line)

        return "\n".join(result)

    @classmethod
    def _fix_blockquotes(cls, text: str) -> str:
        """修复引用块格式"""
        lines = text.split("\n")
        result = []

        for line in lines:
            # 确保引用块格式正确
            if line.startswith(">"):
                # 确保引用符号后有空格
                if len(line) > 1 and line[1] != " ":
                    line = "> " + line[1:]
            result.append(line)

        return "\n".join(result)

    @classmethod
    def _fix_paragraphs(cls, text: str) -> str:
        """优化段落间距"""
        # 移除多余的空行（超过2个连续换行）
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    @classmethod
    def _restore_inline_codes(cls, text: str, inline_codes: dict) -> str:
        """恢复行内代码"""
        for idx, code in inline_codes.items():
            placeholder = cls.INLINE_CODE_PLACEHOLDER.format(idx)
            # 飞书 lark_md 中行内代码不需要转义反引号
            # 只需要确保代码内容不会破坏格式
            safe_code = code.replace("\n", " ")
            text = text.replace(placeholder, f"`{safe_code}`")
        return text

    @classmethod
    def _restore_code_blocks(cls, text: str, code_blocks: dict) -> str:
        """恢复代码块（转换为飞书兼容格式）

        飞书 lark_md 不支持 ```代码块```，也不支持引用块内嵌套行内代码。
        最佳方案：使用纯文本块，用缩进和语言标签标识。
        """
        for idx, (lang, code) in code_blocks.items():
            placeholder = cls.CODE_BLOCK_PLACEHOLDER.format(idx)

            # 清理代码内容
            code_lines = code.strip().split("\n")

            # 构建代码块
            block_parts = []

            # 添加语言标签（如果有）
            if lang:
                block_parts.append(f"**`{lang}`**")
                block_parts.append("")

            # 使用引用块格式，但内部不使用 `code` 格式
            # 避免飞书渲染问题
            for line in code_lines:
                # 转义可能导致问题的特殊字符
                safe_line = line.replace("`", "'")
                block_parts.append(f"> {safe_line}")

            # 添加前后空行
            block = "\n\n" + "\n".join(block_parts) + "\n\n"
            text = text.replace(placeholder, block)

        return text
