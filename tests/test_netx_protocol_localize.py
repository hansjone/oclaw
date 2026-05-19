import unittest

from runtime.tools.experts.network_ops import netx_tools as nt


class NetxProtocolLocalizeTests(unittest.TestCase):
    def test_localize_protocol_summary_to_en(self) -> None:
        data = {
            "protocol_summary": [
                {"key": "其他", "count": 1},
                {"key": "时钟", "count": 2},
                {"key": "OTN/光", "count": 3},
                {"key": "电源", "count": 4},
                {"key": "IP/MPLS", "count": 5},
            ]
        }
        out = nt._localize_netx_payload(dict(data), lang="en")
        keys = [r["key"] for r in out["protocol_summary"]]
        self.assertEqual(keys, ["Other", "Clock", "OTN/Optical", "Power", "IP/MPLS"])

    def test_zh_payload_unchanged(self) -> None:
        data = {"protocol_summary": [{"key": "其他", "count": 1}]}
        out = nt._localize_netx_payload(dict(data), lang="zh")
        self.assertEqual(out["protocol_summary"][0]["key"], "其他")


if __name__ == "__main__":
    unittest.main()
