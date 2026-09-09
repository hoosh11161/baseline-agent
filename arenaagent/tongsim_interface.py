"""TongSim 客户端接口契约与空间数据类型。

接口按角色生命周期、感知查询、视角控制、移动、抓取放置和场景交互分类。
本模块只声明抽象接口；远程调用实现见 tongsim_grpc_client.TongSimGrpcClient。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


# ------------------------------------------------------------------ #
# 空间数据类型
# ------------------------------------------------------------------ #

@dataclass
class Location:
    """仿真世界中的 XYZ 坐标，字段名称保留大写以兼容现有调用。

    Attributes:
        X: X 轴坐标。
        Y: Y 轴坐标。
        Z: Z 轴坐标。

    坐标单位和轴方向由服务端约定。本类只保存数据，不进行单位换算或合法性校验；
    不会自动转换为 RPC 坐标参数，调用时应按具体实现传入列表或字典。
    """

    X: float
    Y: float
    Z: float


@dataclass
class Rotation:
    """物体旋转的欧拉角表示，用于放置接口的旋转参数。

    Attributes:
        roll: 滚转角，单位为度。
        yaw: 偏航角，单位为度。
        pitch: 俯仰角，单位为度。

    旋转轴及正方向遵循服务端约定。gRPC 放置接口按字段名称序列化本对象；
    spawn_character 的 rot 则要求可迭代序列，不能直接传入本数据类。
    """

    roll: float
    yaw: float
    pitch: float


class TongSimInterface(ABC):
    """面向客户端的 TongSim 感知与动作抽象接口。

    通用约定：
        character_id 是 spawn_character 返回的角色 ID。
        动作接口的物体 ID 均为服务端分配的映射 ID，不暴露 TongSim SDK 原始 ID。
        应使用同一角色感知结果中的映射 ID；角色销毁或服务端会话重置后不应复用。
        which_hand 是服务端定义的手部索引，本接口不规定左右手编号。
        坐标通常使用 [x, y, z] 序列；具体格式、距离单位和可达性由服务端约定。

    返回与错误：
        感知、持物查询、角色创建和关闭分别声明自己的返回形式。
        其余接口在当前 TongSimGrpcClient 中返回服务端响应字典，不统一约定业务字段。
        收到字典不等于动作成功，调用方应按服务端协议检查业务结果。
        除 close 的清理流程外，当前 gRPC 实现不会在这些方法中拦截远程调用异常。

    实现要求：
        子类必须实现全部抽象方法；此处不执行动作，也不负责参数校验。
        以下分类仅用于组织接口，不改变方法名、参数默认值或抽象方法契约。
    """

    # ------------------------------------------------------------------ #
    # 一、角色与连接生命周期
    # ------------------------------------------------------------------ #

    @abstractmethod
    def spawn_character(
        self,
        loc,
        rot,
        desired_name,
        fov: float = 120.0,
        width: int = 720,
        height: int = 1000,
        camera_name_suffix: str | None = None,
        camera_stream_id: str | None = None,
        spawn_extra_camera: bool = False,
    ) -> str:
        """创建角色，并配置其感知摄像机。

        Args:
            loc: 出生位置的 XYZ 三元素序列；gRPC 实现通过 list(loc) 转换。
            rot: 初始旋转序列；gRPC 实现通过 list(rot) 透传，分量顺序由服务端约定。
            desired_name: 期望的角色名称；实际命名及冲突处理由服务端决定。
            fov: 摄像机视场角，默认 120.0；角度约定由服务端定义。
            width: 摄像机图像宽度（像素），默认 720，不是最终组合图宽度。
            height: 摄像机图像高度（像素），默认 1000。
            camera_name_suffix: 可选摄像机名称后缀；None 表示不指定。
            camera_stream_id: 可选摄像机流标识；None 表示不指定。
            spawn_extra_camera: 是否请求创建额外摄像机，默认 False；具体用途由服务端定义。

        Returns:
            角色 ID 字符串，供后续操作使用；当前 gRPC 实现在响应缺少该字段时返回空字符串。

        Notes:
            loc、rot 应传入可迭代序列；本模块的 Location、Rotation 数据类本身不可迭代。
        """
        raise NotImplementedError()

    @abstractmethod
    def destory_character(self, character_id=None):
        """销毁角色，并请求服务端清理相关资源。

        Args:
            character_id: 待销毁角色 ID；None 在当前 gRPC 实现中发送为空字符串，销毁范围由服务端决定。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            方法名 destory_character 保留历史拼写，以兼容已有调用方；请勿改为 destroy_character。
        """
        raise NotImplementedError()

    @abstractmethod
    def close(self) -> None:
        """关闭客户端连接并释放相关资源。

        Returns:
            None。

        Notes:
            当前 gRPC 实现停止心跳线程、尝试调用服务端 close，然后关闭通信通道。
            服务端 close 调用异常会被该实现忽略；本接口不保证关闭后的客户端可以再次使用。
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------ #
    # 二、感知与状态查询
    # ------------------------------------------------------------------ #

    @abstractmethod
    def acquire_first_person_perception(
        self,
        character_id,
        width: int | None = None,
        height: int | None = None,
    ) -> dict[str, Any]:
        """获取第一人称组合图及映射后的可见物体信息。

        Args:
            character_id: 需要获取感知结果的角色 ID，由 spawn_character 返回。
            width: 最终组合图宽度（像素）；与 height 同时指定，None 表示不指定缩放尺寸。
            height: 最终组合图高度（像素）；与 width 同时指定，None 表示不指定缩放尺寸。

        Returns:
            感知字典：image 为 Base64 编码的 JPEG 组合图，objects 为物体信息列表。
            组合图左侧为 RGB 图，右侧为映射 ID 分割图；objects 中的 object_id 可用于物体操作。

        Notes:
            默认不缩放：组合图宽度为摄像机宽度的 2 倍，高度等于摄像机高度。
            按 spawn_character 默认摄像机 720×1000 计算，默认组合图为 1440×1000。
            VLMAgent 默认使用 1280×720 摄像机，对应组合图为 2560×720。
            当前 gRPC 客户端仅透传尺寸，尺寸合法性及错误响应由服务端处理。
        """
        raise NotImplementedError()

    @abstractmethod
    def has_object_in_hand(self, character_id) -> tuple[bool, int | None]:
        """查询角色是否持有物体，以及持物的手部索引。

        Args:
            character_id: 需要查询持物状态的角色 ID。

        Returns:
            (has_object, hand_idx)：第一项为是否持物，第二项为手部索引或 None。

        Notes:
            不返回物体名称或物体 ID，也不枚举双手状态。
            当前 gRPC 实现在响应缺少 has_object 时使用 False，缺少 hand_idx 时使用 None。
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------ #
    # 三、视角与指向控制
    # ------------------------------------------------------------------ #

    @abstractmethod
    def look_at_location(
        self, character_id, target_location, is_cancel: bool = False, execute_immediately: bool = False
    ):
        """使角色看向指定位置，或取消看向动作。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            target_location: 仿真世界中的 XYZ 坐标，例如 [x, y, z]；单位由服务端约定。
            is_cancel: 是否请求取消该看向动作，默认 False。
            execute_immediately: 是否请求立即执行，默认 False；具体调度行为由服务端决定。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            取消动作时仍按当前签名传入 target_location；是否使用该坐标由服务端决定。
        """
        raise NotImplementedError()

    @abstractmethod
    def look_at_object(self, character_id, object_id: str, is_cancel: bool = False):
        """使角色看向指定物体，或取消看向动作。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            object_id: 目标物体在当前角色感知结果中的映射 ID。
            is_cancel: 是否请求取消该看向动作，默认 False。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    @abstractmethod
    def point_at_object(self, character_id, object_id: str, is_cancel: bool = False, which_hand: int = 0):
        """使用指定手指向物体，或取消指向动作。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            object_id: 被指向物体的映射 ID。
            is_cancel: 是否请求取消该指向动作，默认 False。
            which_hand: 手部索引，默认 0；左右手编号及有效取值由服务端定义。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------ #
    # 四、移动与转向
    # ------------------------------------------------------------------ #

    @abstractmethod
    def move_to_location(self, character_id, target_location, stop_distance: float = 0.5):
        """导航到指定位置，并使用给定的停止距离。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            target_location: 仿真世界中的 XYZ 坐标，例如 [x, y, z]；单位由服务端约定。
            stop_distance: 到达目标附近时采用的停止距离，默认 0.5；单位及判定规则由服务端定义。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    @abstractmethod
    def move_forward(self, character_id, distance: float):
        """沿角色当前前方移动指定距离。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            distance: 前进距离；单位及是否支持负数由服务端定义。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    @abstractmethod
    def turn_in_degree(self, character_id, degree):
        """使角色按指定角度转向。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            degree: 转向角度，单位为度；正负方向及旋转轴由服务端定义。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    @abstractmethod
    def move_to_object(self, character_id, object_id: str):
        """导航到指定物体附近。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            object_id: 目标物体的映射 ID；具体到达位置由服务端确定。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    @abstractmethod
    def move_to_npc(self, character_id, name: str):
        """按 NPC 名称导航到对应角色附近。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            name: 目标 NPC 的资产名称；服务端负责查找对应实体，不使用物体映射 ID。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------ #
    # 五、物体抓取与放置
    # ------------------------------------------------------------------ #

    @abstractmethod
    def move_and_take_object(
        self,
        character_id,
        object_id: str,
        which_hand: int = 0,
        movable_object_ids: list[str] | None = None,
    ):
        """移动到目标物体附近，并使用指定手抓取。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            object_id: 待抓取物体的映射 ID。
            which_hand: 手部索引，默认 0；左右手编号及有效取值由服务端定义。
            movable_object_ids: 历史兼容参数，默认 None；服务端忽略该参数，不用于限制可抓取物体。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    @abstractmethod
    def move_and_take_puzzle_piece(self, character_id, piece_object_id: str, which_hand: int = 0):
        """移动并抓取指定拼图片。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            piece_object_id: 待抓取拼图片的映射 ID。
            which_hand: 手部索引，默认 0；左右手编号及有效取值由服务端定义。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            这是拼图场景的专用抓取入口；具体抓取流程由服务端实现。
        """
        raise NotImplementedError()

    @abstractmethod
    def put_down_sth(
        self,
        character_id,
        target_location,
        target_rotation: Rotation | None = None,
        auto_rotate: bool = False,
        force_locate: bool = False,
    ):
        """将手中物体放到指定位置，由服务端自动选择持物的手。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            target_location: 仿真世界中的 XYZ 坐标，例如 [x, y, z]；单位由服务端约定。
            target_rotation: 放置旋转，使用 Rotation（欧拉角，单位为度）；None 时由服务端自动调整朝向。
            auto_rotate: 是否请求自动调整物体朝向，默认 False；未指定 target_rotation 时服务端自动启用。
            force_locate: 是否请求强制放置到目标位置，默认 False；具体执行方式由服务端决定。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            角色需要已持有物体；空手时服务端返回错误。
            此接口不接收 which_hand；需要显式指定手并先移动时，使用 move_and_put_down。
        """
        raise NotImplementedError()

    @abstractmethod
    def move_and_put_down(
        self,
        character_id,
        move_target_location,
        put_target_location,
        which_hand: int = 0,
        put_rotation: Rotation | None = None,
    ):
        """先移动到角色目标位置，再将指定手中的物体放到放置位置。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            move_target_location: 角色的导航目标 XYZ 坐标。
            put_target_location: 物体最终放置的 XYZ 坐标，与角色导航目标分别指定。
            which_hand: 手部索引，默认 0；左右手编号及有效取值由服务端定义。
            put_rotation: 可选物体放置旋转，使用 Rotation；None 时不指定，交由服务端处理。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            调用前指定手应已持有物体；坐标单位和动作可达性由服务端约定。
        """
        raise NotImplementedError()

    @abstractmethod
    def move_and_put_down_object_in_container(self, character_id, which_hand: int = 0):
        """移动并将指定手中的物体放入容器。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            which_hand: 手部索引，默认 0；左右手编号及有效取值由服务端定义。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            调用前指定手应已持有物体。
            本接口没有容器 ID 或位置参数，容器选择和导航目标由服务端确定。
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------ #
    # 六、生活动作与场景交互
    # ------------------------------------------------------------------ #

    @abstractmethod
    def pour_water(self, character_id, object_id: str, location, which_hand: int = 0):
        """请求角色执行倒水动作。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            object_id: 倒水动作关联物体的映射 ID；源容器或目标物体的具体语义由服务端定义。
            location: 倒水动作使用的 XYZ 位置；具体定位语义由服务端定义。
            which_hand: 手部索引，默认 0；左右手编号及有效取值由服务端定义。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    @abstractmethod
    def slice_food(self, character_id, object_id: str, location):
        """请求角色执行切食物动作。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            object_id: 切食物动作关联物体的映射 ID。
            location: 切食物动作使用的 XYZ 位置；具体定位语义由服务端定义。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            工具、持物状态等动作前置条件由服务端判定。
        """
        raise NotImplementedError()

    @abstractmethod
    def wash_hands(self, character_id, faucet_object_id: str):
        """使用指定水龙头执行洗手动作。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            faucet_object_id: 场景中目标水龙头的映射 ID。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    @abstractmethod
    def wash_object_in_hand(self, character_id, faucet_object_id: str):
        """使用指定水龙头清洗手中物体。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            faucet_object_id: 场景中目标水龙头的映射 ID。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            角色应已持有待清洗物体；使用哪只手及动作前置条件由服务端判断。
        """
        raise NotImplementedError()

    @abstractmethod
    def mop_floor(self, character_id, dirt_id: str):
        """对指定污渍执行拖地动作。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            dirt_id: 目标污渍物体的映射 ID。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            所需工具及角色状态由服务端判定。
        """
        raise NotImplementedError()

    @abstractmethod
    def sit_down_to_object(self, character_id, object_id: str):
        """请求角色坐到指定物体上。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            object_id: 目标座椅等可坐物体的映射 ID；是否可坐由服务端判定。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。
        """
        raise NotImplementedError()

    @abstractmethod
    def rest(self, character_id):
        """请求角色执行休息动作。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            休息的姿态、时长及对当前动作的影响由服务端定义。
        """
        raise NotImplementedError()

    @abstractmethod
    def speak_to_npc(self, character_id, target: str, content: str):
        """请求角色向目标 NPC 说出指定内容。

        Args:
            character_id: 执行操作的角色 ID，由 spawn_character 返回。
            target: 目标 NPC 标识字符串；具体名称或标识格式由服务端约定。
            content: 向 NPC 表达的文本内容。

        Returns:
            当前 gRPC 实现返回服务端响应字典；业务状态和字段以具体服务端为准。

        Notes:
            返回值为动作响应字典；本接口不约定返回 NPC 的回复文本。
        """
        raise NotImplementedError()
