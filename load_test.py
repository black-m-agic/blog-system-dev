from locust import HttpUser, task, between

class BlogUser(HttpUser):
    wait_time = between(1, 3)  # 模拟用户在操作之间的等待时间
    
    @task(3)  # 权重为3，访问首页的频率更高
    def index_page(self):
        """测试首页访问"""
        self.client.get("/")
    
    @task(2)  # 权重为2
    def article_pages(self):
        """测试文章页面访问"""
        # 测试不同文章
        for article_id in [1, 2, 3, 4, 5]:
            self.client.get(f"/article/{article_id}")
    
    @task(1)  # 权重为1
    def category_pages(self):
        """测试分类页面访问"""
        # 测试不同分类
        for category_id in [1, 2, 3, 4, 5]:
            self.client.get(f"/category/{category_id}")
    
    @task(1)  # 权重为1
    def tag_pages(self):
        """测试标签页面访问"""
        # 测试不同标签
        for tag_id in [1, 2, 3, 4, 5]:
            self.client.get(f"/tag/{tag_id}")

# 运行命令：locust -f load_test.py --host=http://localhost:8080
# 然后在浏览器中打开 http://localhost:8089 开始测试
