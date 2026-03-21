import os
import re
import json
import frontmatter
import bibtexparser
from pathlib import Path
from PIL import Image, ImageOps

# 路径配置 (依据脚本当前所在位置推导根目录)
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
CONFIG_PATH = ROOT_DIR / "config.json"
RESEARCHERS_PATH = SCRIPT_DIR.parent / "cg_researchers_homepage.json" # 研究者主页JSON路径

# 加载配置
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)

# 加载研究者主页映射数据
RESEARCHERS = {}
if RESEARCHERS_PATH.exists():
    with open(RESEARCHERS_PATH, 'r', encoding='utf-8') as f:
        RESEARCHERS = json.load(f)
else:
    print(f"未找到 {RESEARCHERS_PATH}，将跳过作者主页链接生成。")

REPO_PATH = ROOT_DIR / "database"
PAPERS_DIR = REPO_PATH / CONFIG.get("database_repo_papers_dir")
IMG_SRC_DIR = REPO_PATH / CONFIG.get("database_repo_img_dir")
IMG_DEST_DIR = ROOT_DIR / ".img"
README_PATH = ROOT_DIR / "README.md"
JSON_OUTPUT = ROOT_DIR / "extracted_papers.json"

print("SCRIPT_DIR: ", SCRIPT_DIR)
print("ROOT_DIR: ", ROOT_DIR)
print("REPO_PATH: ", REPO_PATH)
print("PAPERS_DIR: ", PAPERS_DIR)
print("IMG_SRC_DIR: ", IMG_SRC_DIR)
print("IMG_DEST_DIR: ", IMG_DEST_DIR)
print("README_PATH: ", README_PATH)
print("JSON_OUTPUT: ", JSON_OUTPUT)

def clean_bibtex_string(s):
    """去除 bibtex 中常见的花括号"""
    return s.replace('{', '').replace('}', '').replace('\n', ' ').strip()


def parse_bibtex(bibtex_str):
    if not bibtex_str.strip():
        return {}
    try:
        bib_database = bibtexparser.loads(bibtex_str)
        if not bib_database.entries:
            return {}
        entry = bib_database.entries[0]

        raw_doi = entry.get('doi', '')
        raw_url = entry.get('url', '')
        doi_url = raw_url if raw_url else (f"https://doi.org/{raw_doi}" if raw_doi else "")

        return {
            "title": clean_bibtex_string(entry.get('title', 'Unknown Title')),
            "author": clean_bibtex_string(entry.get('author', 'Unknown Author')),
            "venue": clean_bibtex_string(entry.get('journal', '') or entry.get('booktitle', '')),
            "doi_url": doi_url,
            "year": clean_bibtex_string(entry.get('year', '-')),
            "month": clean_bibtex_string(entry.get('month', ''))
        }
    except Exception as e:
        print(f"Bibtex 解析错误: {e}")
        return {}


def crop_and_save_image(src_path, dest_path, target_width=500, target_height=300):
    """等比缩放图片以填满目标尺寸，并居中裁剪超出部分"""
    try:
        if not src_path.exists():
            return False

        IMG_DEST_DIR.mkdir(parents=True, exist_ok=True)

        with Image.open(src_path) as img:
            # 转换为RGB格式以防PNG透明通道导致保存JPEG报错
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # ImageOps.fit 完美实现“等比拉伸填满并居中裁剪”
            # centering=(0.5, 0.5) 代表从中心点向外裁剪
            img_cropped = ImageOps.fit(
                img,
                (target_width, target_height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5)
            )

            img_cropped.save(dest_path)
            return True
    except Exception as e:
        print(f"图片处理失败 {src_path}: {e}")
        return False


def process_md_files():
    results = []

    # 从配置中读取过滤关键字
    target_tag = CONFIG.get("filter_tag", "").lower()

    if not PAPERS_DIR.exists():
        print(f"目录不存在: {PAPERS_DIR}")
        return results

    for md_file in PAPERS_DIR.rglob("*.md"):
        try:
            post = frontmatter.load(md_file)
            metadata = post.metadata

            # 修复tags提取：兼容 tag 和 tags 键，确保转换为列表
            raw_tags = metadata.get('tags') or metadata.get('tag') or []
            if isinstance(raw_tags, str):
                tags = [t.strip() for t in raw_tags.split(',')]
            else:
                tags = [str(t) for t in raw_tags]

            # 1. 过滤：只提取 tags 中包含 directional 的 md 文件
            if not any(target_tag in t.lower() for t in tags):
                continue

            # 提取 frontmatter 的属性到 properties
            properties = {
                "bibtex": metadata.get('bibtex', ''),
                "code": metadata.get('code', ''),
                "data": metadata.get('data', ''),
                "project": metadata.get('project', ''),
                "slide": metadata.get('slide', ''),
                "supplemental": metadata.get('supplemental', ''),
                "tags": tags,
                "teaser": metadata.get('teaser', '')
            }

            bibtex_raw = properties["bibtex"]
            bibtex_parsed = parse_bibtex(bibtex_raw)

            # 图片处理逻辑
            img_dest_rel_path = ""
            if properties['teaser']:
                img_pic = IMG_SRC_DIR / properties['teaser']

                # --- 新增检查与打印逻辑 ---
                if not img_pic.exists():
                    print(f"⚠️ 图片未找到，请检查路径是否正确: {img_pic}")
                else:
                    dest_img_name = f"{md_file.stem}_{properties['teaser']}"
                    dest_img = IMG_DEST_DIR / dest_img_name

                    if crop_and_save_image(img_pic, dest_img):
                        img_dest_rel_path = f".img/{dest_img_name}"

            paper_info = {
                "filename": md_file.name,
                "properties": properties,
                "bibtex_parsed": bibtex_parsed,
                "img_path": img_dest_rel_path
            }

            results.append(paper_info)
            print(f"成功处理文件: {md_file.name}")

        except Exception as e:
            print(f"处理文件 {md_file.name} 时出错: {e}")

    return results


def generate_readme(data):
    # 月份解析与多级排序逻辑
    def get_month_num(m_str):
        if not m_str: return 0
        m_str = m_str.lower()
        months_map = {
            'jan':1, 'feb':2, 'mar':3, 'apr':4, 'may':5, 'jun':6,
            'jul':7, 'aug':8, 'sep':9, 'oct':10, 'nov':11, 'dec':12,
            '1':1, '2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, '11':11, '12':12
        }
        for k, v in months_map.items():
            if k in m_str: return v
        return 0

    def sort_key(item):
        bib = item.get("bibtex_parsed", {})
        year_str = bib.get("year", "0")
        year = int(year_str) if year_str.isdigit() else 0
        month_num = get_month_num(bib.get("month", ""))
        return (year, month_num)

    data.sort(key=sort_key, reverse=True)

    # ================= 新增需求 1: 提取所有 Tags 并去重排序 =================
    target_tag = CONFIG.get("filter_tag", "").lower()
    all_tags = set()
    for item in data:
        for tag in item.get('properties', {}).get('tags', []):
            if tag.strip():
                all_tags.add(tag.strip())
    
    # 将 tag 分为 target_tag 和其他 tags
    actual_target_tag = None
    other_tags = []
    for tag in all_tags:
        if tag.lower() == target_tag:
            actual_target_tag = tag # 保留原始大小写
        else:
            other_tags.append(tag)
            
    other_tags.sort(key=lambda x: x.lower()) # 剩余 tag 按字母顺序排列
    
    # 组装最终的 tags 列表，确保 filter_tag 在第一位
    final_tags_list = []
    if actual_target_tag:
        final_tags_list.append(actual_target_tag)
    final_tags_list.extend(other_tags)
    
    # 生成 tags 字符串 (例如: `tag1` `tag2`)
    all_tags_md = " ".join([f"`{t}`" for t in final_tags_list])

    # ================= 新增需求 2: 准备作者链接替换函数 =================
    # 1. 预处理研究者名单：生成包含三种格式的搜索列表
    search_list = []
    for raw_name, url in RESEARCHERS.items():
        # 添加原始格式 (例如: "Wang, Xiaoming")
        search_list.append((raw_name, url))
        
        if "," in raw_name:
            parts = [p.strip() for p in raw_name.split(",")]
            if len(parts) == 2:
                last, first = parts[0], parts[1]
                # 添加变体: "Xiaoming Wang" (名 姓)
                search_list.append((f"{first} {last}", url))
                # 添加变体: "Wang Xiaoming" (姓 名)
                search_list.append((f"{last} {first}", url))

    # 2. 按名字长度降序排序，防止短名字（如 "Li"）误匹配长名字（如 "Li, Hao"）
    search_list.sort(key=lambda x: len(x[0]), reverse=True)

    def linkify_authors(author_str):
        if not search_list:
            return author_str
        
        # BibTeX 中的作者通常用 " and " 分隔
        author_list = [a.strip() for a in author_str.split(" and ")]
        linked_list = []
        
        for author_segment in author_list:
            matched = False
            for name_variant, url in search_list:
                # 使用正则表达式进行【完整单词】匹配
                # \b 表示单词边界，确保 "Li" 不会匹配 "Liang"
                # re.escape 会处理名字中可能存在的特殊字符（如逗号）
                pattern = r'\b' + re.escape(name_variant) + r'\b'
                
                if re.search(pattern, author_segment):
                    # 使用 re.sub 进行替换，count=1 确保只替换一次
                    author_segment = re.sub(pattern, f"[{name_variant}]({url})", author_segment, count=1)
                    matched = True
                    break # 匹配到一个变体后跳出，处理下一个作者
            linked_list.append(author_segment)
        
        return " and ".join(linked_list)

    # ================= 构建 README 内容 =================
    lines = [
        CONFIG.get("readme_header", "# Papers"),
        "\n\n",
        "### All Tags\n",
        all_tags_md,      # 在此处插入所有 Tags
        "\n\n",
        "| Teaser | Information |",
        "| :--- | :--- |"
    ]

    for item in data:
        bib = item.get('bibtex_parsed', {})
        props = item.get('properties', {})

        # 处理左栏：图片
        pic_md = f"<img src='{item['img_path']}' width='500' height='300' style='object-fit: cover;'>" if item['img_path'] else "No Image"

        # 处理右栏：信息
        title = f"**{bib.get('title', 'Unknown Title')}**"
        
        # ================= 应用作者替换逻辑 =================
        raw_author = bib.get('author', 'Unknown Author')
        linked_author = linkify_authors(raw_author)
        author = f"*{linked_author}*"

        # 将 tags 列表转化为 `tag0`, `tag1` ... 的格式
        tags_list = props.get('tags', [])
        tags_str = " ".join([f"`{t.strip()}`" for t in tags_list])

        # 发表日期与期刊
        date_str = f"{bib.get('year', '')} {bib.get('month', '')}".strip()
        venue = bib.get('venue', '')
        date_venue = f"{date_str}{', ' + venue if venue else ''}"

        # 生成按钮链接
        links = []
        if bib.get('doi_url'): links.append(f"[[doi]]({bib.get('doi_url')})")
        if props.get('project'): links.append(f"[[project]]({props.get('project')})")
        if props.get('code'): links.append(f"[[code]]({props.get('code')})")
        if props.get('slide'): links.append(f"[[slide]]({props.get('slide')})")
        if props.get('supplemental'): links.append(f"[[supplemental]]({props.get('supplemental')})")
        if props.get('data'): links.append(f"[[data]]({props.get('data')})")
        links_str = " &nbsp; ".join(links)

        # 拼接表格行 (<br>换行)
        info_md = f"{title}<br>{author}<br>{date_venue}<br>tags: {tags_str}<br>{links_str}"
        lines.append(f"| {pic_md} | {info_md} |")

    with open(README_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == "__main__":
    print("开始处理论文数据...")
    extracted_data = process_md_files()

    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)

    print(f"数据提取完成，共 {len(extracted_data)} 篇，开始生成 README.md...")
    generate_readme(extracted_data)
    print("README.md 生成完成！")
