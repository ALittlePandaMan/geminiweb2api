import orjson as json

from ..constants import GRPC
from ..types import RPCData
from ..utils import extract_json_from_response, get_nested_value


class ResearchMixin:
    """
    Mixin class providing account capability inspection helpers.
    """

    async def inspect_account_status(self) -> dict:
        """Probe account/model capability RPCs and return raw parsed snapshots."""

        probes = [
            ("activity", GRPC.BARD_SETTINGS, '[[["bard_activity_enabled"]]]'),
            (
                "bootstrap",
                GRPC.DEEP_RESEARCH_BOOTSTRAP,
                '["en",null,null,null,4,null,null,[2,4,7,15],null,[[5]]]',
            ),
            ("model_state", GRPC.DEEP_RESEARCH_MODEL_STATE, "[[[1,4],[6,6],[1,15]]]"),
            ("quota", GRPC.DEEP_RESEARCH_MODEL_STATE, "[[[1,11],[2,11],[6,11]]]"),
            ("caps", GRPC.DEEP_RESEARCH_CAPS, "[]"),
        ]

        result: dict = {
            "source_path": "/app",
            "account_path": getattr(self, "account_path", ""),
            "rpc": {},
        }

        for probe_name, rpcid, payload in probes:
            try:
                response = await self._batch_execute(
                    [RPCData(rpcid=rpcid, payload=payload)], close_on_error=False
                )
                parsed = []
                reject_code = None
                parts = extract_json_from_response(response.text)
                for part in parts:
                    if get_nested_value(part, [0]) != "wrb.fr":
                        continue
                    if get_nested_value(part, [1]) != rpcid:
                        continue
                    code = get_nested_value(part, [5, 0])
                    if isinstance(code, int):
                        reject_code = code
                    body = get_nested_value(part, [2])
                    if isinstance(body, str):
                        try:
                            parsed.append(json.loads(body))
                        except json.JSONDecodeError:
                            parsed.append(body)
                    elif body is not None:
                        parsed.append(body)

                result["rpc"][probe_name] = {
                    "rpcid": rpcid,
                    "ok": True,
                    "status_code": response.status_code,
                    "parsed": parsed,
                    "reject_code": reject_code,
                    "raw_preview": response.text[:300],
                }
            except Exception as e:
                result["rpc"][probe_name] = {
                    "rpcid": rpcid,
                    "ok": False,
                    "error": f"{type(e).__name__}: {e}",
                }

        rejected = [
            name
            for name, probe in result["rpc"].items()
            if isinstance(probe, dict) and probe.get("reject_code") == 7
        ]
        dr_probes = ("bootstrap", "model_state", "caps")
        dr_available = all(
            result["rpc"].get(p, {}).get("ok", False)
            and result["rpc"].get(p, {}).get("reject_code") is None
            for p in dr_probes
        )

        result["summary"] = {
            "deep_research_feature_present": dr_available,
            "rejected_probes": rejected,
        }

        return result
