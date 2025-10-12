import arxiv
import requests
from datetime import datetime

print("=" * 60)
print("🧪 arXiv 连接测试")
print("=" * 60)

# 测试 1: 检查 arXiv 网站是否可访问
print("\n📡 测试 1: 检查 arXiv 网站可达性")
try:
    response = requests.get('https://arxiv.org', timeout=10)
    if response.status_code == 200:
        print("✅ arXiv 网站可访问")
    else:
        print(f"⚠️ arXiv 返回状态码: {response.status_code}")
except Exception as e:
    print(f"❌ 无法访问 arXiv 网站: {str(e)}")

# 测试 2: 检查 arXiv API 端点
print("\n📡 测试 2: 检查 arXiv API 端点")
try:
    response = requests.get('http://export.arxiv.org/api/query?search_query=all:electron&max_results=1', timeout=10)
    if response.status_code == 200:
        print("✅ arXiv API 端点可访问")
        print(f"   响应长度: {len(response.text)} 字节")
    else:
        print(f"⚠️ API 返回状态码: {response.status_code}")
except Exception as e:
    print(f"❌ 无法访问 arXiv API: {str(e)}")

# 测试 3: 使用 arxiv 库进行简单搜索
print("\n📡 测试 3: 使用 arxiv 库搜索论文")
try:
    client = arxiv.Client()
    
    # 最简单的搜索：只搜索一篇论文
    search = arxiv.Search(
        query='electron',  # 简单关键词
        max_results=3
    )
    
    print("🔍 正在搜索...")
    results = list(client.results(search))
    
    if results:
        print(f"✅ 成功找到 {len(results)} 篇论文")
        for i, result in enumerate(results, 1):
            print(f"\n论文 {i}:")
            print(f"  标题: {result.title[:80]}...")
            print(f"  发布时间: {result.published}")
            print(f"  分类: {result.categories[:3]}")
    else:
        print("⚠️ 未找到论文")
        
except Exception as e:
    print(f"❌ arxiv 库搜索失败: {str(e)}")
    import traceback
    print("\n详细错误信息:")
    traceback.print_exc()

# 测试 4: 测试特定分类搜索
print("\n📡 测试 4: 测试 cs.AI 分类搜索")
try:
    client = arxiv.Client()
    
    search = arxiv.Search(
        query='cat:cs.AI',
        max_results=3,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    
    print("🔍 正在搜索 cs.AI 分类...")
    results = list(client.results(search))
    
    if results:
        print(f"✅ 成功找到 {len(results)} 篇 cs.AI 论文")
        for i, result in enumerate(results, 1):
            print(f"\n论文 {i}:")
            print(f"  标题: {result.title[:80]}...")
            print(f"  分类: {result.categories}")
    else:
        print("⚠️ 未找到 cs.AI 论文")
        
except Exception as e:
    print(f"❌ cs.AI 分类搜索失败: {str(e)}")

# 测试 5: 测试多分类搜索
print("\n📡 测试 5: 测试多分类 OR 查询")
try:
    client = arxiv.Client()
    
    search = arxiv.Search(
        query='cat:cs.AI OR cat:cs.CV OR cat:cs.CL',
        max_results=5,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    print("🔍 正在搜索 cs.AI OR cs.CV OR cs.CL...")
    results = list(client.results(search))
    
    if results:
        print(f"✅ 成功找到 {len(results)} 篇论文")
        for i, result in enumerate(results, 1):
            print(f"\n论文 {i}:")
            print(f"  标题: {result.title[:60]}...")
            print(f"  分类: {result.categories[:3]}")
            print(f"  发布: {result.published.strftime('%Y-%m-%d')}")
    else:
        print("⚠️ 未找到论文")
        
except Exception as e:
    print(f"❌ 多分类搜索失败: {str(e)}")

print("\n" + "=" * 60)
print("🏁 测试完成")
print("=" * 60)

# 网络诊断信息
print("\n🔧 网络诊断建议:")
print("1. 如果所有测试都失败，可能是网络连接问题")
print("2. 如果只有 API 测试失败，可能需要代理或 VPN")
print("3. 如果找不到论文，可能是查询条件问题")
print("4. 在中国大陆访问 arXiv 可能较慢，建议使用镜像:")
print("   - ar5iv.org (HTML版本)")
print("   - arxiv.org/list/cs.AI/recent (直接访问分类列表)")
