# yun

yun 是基于 [slowdown](http://slowdown.pyforce.com.cn/) 开发的一款在线文件服务，前端 [APP](https://github.com/xunpu/yun-app)

slowdown 路由配置文件：
```
<modules>
    load com.pyforce.runtime
    load yun.runtime
</modules>

<routers>
    <router SERVER>
        pattern ^(?P<YUN>yun)\.test\.com(?:\:\d{1,6})?$$
        <host YUN>
            pattern ^/api/account(?P<ACCOUNT>/.*)$$
            <path ACCOUNT>
                handler yun.account
            </path>
            pattern ^/api(?P<API>/.*)$$
            <path API>
                handler yun.api
            </path>
            pattern ^(?P<ALL>/.*)$$
            <path ALL>
                handler yun.static
            </path>
        </host>
  </router>
</routers>
    
<servers>
    <http HTTP>
        address 0.0.0.0:8080
        router  SERVER
    </http>
</servers>
```
