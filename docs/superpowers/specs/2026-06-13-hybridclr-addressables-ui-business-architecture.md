# HybridCLR + Addressables + 短连接 UI/业务架构

## 目标

本设计把游戏工程拆成三条稳定边界：

- `HybridCLR`：承载可热更的 Feature 业务逻辑、Feature UI 和 ViewModel。
- `Addressables`：承载 UI Prefab、图集、字体、配置、热更 DLL 和 AOT metadata 等可下载资源。
- HTTP 短连接：只属于 `Network` / `Data` 层，UI 不直接调用 `UnityWebRequest`。

当前实现只落地 AOT 侧框架接口、默认降级实现、HotUpdate 示例边界和 EditMode 测试。`Addressables` 与 `HybridCLR` 包安装、ProjectSettings、Addressables Group、Prefab 和 `.meta` 生成必须作为后续 Unity Adapter 执行计划处理。

## 分层

```text
Assets/_Project/Runtime/
  Boot/          # GameLauncher 和 AOT 服务装配
  Assets/        # IAssetService 与 AddressablesAssetService 边界
  Network/       # INetworkClient、短连接 HTTP、DTO 序列化
  UI/            # UIManager、UIView、UIUtil、UGUI/TMP 扩展
  Update/        # HybridCLR 热更加载边界

Assets/_Project/HotUpdate/
  Shared/        # ViewModel 基类、热更共享 DTO
  Features/      # Feature Domain/Application/UI

Assets/_Project/Tests/EditMode/
  Assets/
  Network/
  UI/
  Update/
  HotUpdate/
```

`Runtime` 是 AOT 固定层。`HotUpdate` 是未来 HybridCLR 的热更程序集边界。普通业务代码不能直接依赖 `Addressables` 或 `UnityWebRequest`，只能依赖 `IAssetService`、`INetworkClient`、`UIManager` 等稳定接口。

## 关键接口

- `IAssetService`：业务和 UI 只按 key 加载资源；当前 `AddressablesAssetService` 在未安装 Addressables 时明确失败，避免静默假成功。
- `INetworkClient`：统一短连接入口，支持 headers、timeout、retry、cancellation 和 `ApiResult<T>`。
- `IHttpTransport`：隔离 `UnityWebRequest`，便于 EditMode 测试网络重试、取消和错误处理。
- `UIManager`：只负责打开、关闭、层级、Prefab 加载和实例生命周期；不得增加 `OpenInventory()`、`OpenShop()` 等业务方法。
- `IUIPrefabRegistry`：集中管理 UI key 到资源 key 的映射，避免 Address key 散落在 Feature 代码里。
- `HybridClrUpdateService`：只定义热更加载流程边界；实际 HybridCLR loader 需要安装包后补充。

## 数据流

```text
UIView
 -> ViewModel / Presenter
 -> Feature Application
 -> Repository / Api
 -> INetworkClient
 -> UnityWebRequestTransport
 -> ApiResult<T>
 -> ViewModel 更新
 -> UIView 刷新
```

UI 只能依赖 Feature Application 或 ViewModel。短连接网络实现属于 AOT `Network` 层；具体 API、DTO、Repository 可以放入 HotUpdate。

## 热更启动流

```text
GameLauncher(AOT)
 -> 配置 IAssetService / INetworkClient / UIManager / HybridClrUpdateService
 -> 初始化 Addressables
 -> 更新 Catalog/Bundle
 -> 加载 AOT metadata
 -> 加载 HotUpdate DLL
 -> 进入 HotUpdate.Entry
```

本次只提供 `GameLauncher.ConfigureAotServices()` 与 `HybridClrUpdateService` 的边界。由于 `HybridCLR` 未安装，默认 loader 为 `null`，调用热更加载时返回 `LoaderUnavailable`。

## AI 约束

- Codex/Agent 可以修改普通 C#、测试和中文 Markdown 文档。
- Codex/Agent 不直接编辑 `.prefab`、`.asset`、`.meta`、ProjectSettings、Addressables Group 或 package manifest。
- 安装 `Addressables`、安装 `HybridCLR`、生成 Addressables 配置、创建 UI Prefab、修改场景都必须先生成 execution plan、risk review，并通过 Unity Editor Adapter 执行。

## 验收

- AOT 框架代码存在于 `Assets/_Project/Runtime`。
- HotUpdate 示例代码存在于 `Assets/_Project/HotUpdate`。
- EditMode 测试覆盖资源释放、Addressables 未安装降级、HTTP headers/retry/cancel、UIManager open/close、HybridCLR loader 缺失、ViewModel 更新。
- Unity 编译和 EditMode 测试需要在打开对应 worktree 的 Unity Editor 后执行。
