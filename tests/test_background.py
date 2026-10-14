import io
import json
from unittest.mock import patch
import unittest
from uibe.background import fetch_us_debt,supplement

class BackgroundTests(unittest.TestCase):
    def response(self,**updates):
        row={'record_date':'2025-01-02','debt_held_public_amt':'32000000000000.00','intragov_hold_amt':'8000000000000.00','tot_pub_debt_out_amt':'40000000000000.00',**updates}
        return io.BytesIO(json.dumps({'data':[row]}).encode())

    def test_source_date_units_and_exact_amounts_preserved(self):
        with patch('uibe.background.urlopen',return_value=self.response()) as request:
            data=fetch_us_debt('2025-01-03')
        self.assertEqual(data['record_date'],'2025-01-02')
        self.assertEqual(data['unit'],'USD')
        self.assertEqual(data['values']['tot_pub_debt_out_amt'],'40000000000000.00')
        self.assertIn('record_date%3Alte%3A2025-01-03',request.call_args.args[0])
        self.assertIn('record_date%3Aeq%3A2025-01-02',data['data_url'])
        self.assertEqual(len(data['record_sha256']),64)
        self.assertEqual(data['kind'],'external_background')

    def test_later_record_and_invalid_totals_rejected(self):
        for updates in [{'record_date':'2025-01-04'},{'tot_pub_debt_out_amt':'50000000000000'},{'tot_pub_debt_out_amt':'NaN'}]:
            with patch('uibe.background.urlopen',return_value=self.response(**updates)):
                with self.assertRaises(ValueError):fetch_us_debt('2025-01-03')

    def test_network_failure_does_not_change_claims_or_create_a_verdict(self):
        original={'relevant':True,'claims':[{'statement':'美国债务超过四十万亿美元'}],'events':[]}
        def failed():raise TimeoutError('network timeout')
        result=supplement(original,fetcher=failed)
        self.assertEqual(result['claims'],original['claims'])
        self.assertNotIn('external_background',original)
        self.assertEqual(result['external_background'][0]['status'],'unavailable')
        self.assertNotIn('verdict',result['external_background'][0])
        unrelated={'relevant':False,'claims':[]}
        self.assertIs(supplement(unrelated,'美国债务',fetcher=failed),unrelated)

if __name__=='__main__':unittest.main()
