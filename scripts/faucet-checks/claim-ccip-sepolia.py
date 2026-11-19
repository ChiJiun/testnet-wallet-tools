import os
import sys,time
sys.path.insert(0,"/home/devspace/projects/testnet-wallet-tools")
from wallet import wallets,rpc,fee_fields,balance
from eth_utils import keccak,to_checksum_address
url="https://ethereum-sepolia-rpc.publicnode.com"
chain=11155111
assert int(rpc(url,"eth_chainId"),16)==chain
account=wallets(1)[0]
beneficiary = os.environ.get("CELO_FAUCET_BENEFICIARY", "")
if account.address.lower() != beneficiary.lower():
    sys.exit("Configured beneficiary must match derived index 0")
target=to_checksum_address("0xFd57b4ddBf88a4e07fF4e34C487b99af2Fe82a05")
data="0x"+keccak(text="drip(address)")[:4].hex()+account.address[2:].lower().zfill(64)
params={"from":account.address,"to":target,"data":data}
gas=int(rpc(url,"eth_estimateGas",[params]),16)*12//10
fees=fee_fields(url)
assert balance(url,account.address)>gas*(fees.get("maxFeePerGas") or fees["gasPrice"])
nonce=int(rpc(url,"eth_getTransactionCount",[account.address,"pending"]),16)
tx=account.sign_transaction(dict(chainId=chain,to=target,data=data,gas=gas,nonce=nonce,value=0,**fees))
txid=rpc(url,"eth_sendRawTransaction",["0x"+tx.raw_transaction.hex()])
print("Chainlink CCIP-BnM submitted:",txid,flush=True)
for _ in range(24):
    receipt=rpc(url,"eth_getTransactionReceipt",[txid])
    if receipt:
        topic="0x"+keccak(text="Transfer(address,address,uint256)").hex()
        recipient="0x"+account.address[2:].lower().zfill(64)
        for log in receipt.get("logs",[]):
            if log["address"].lower()==target.lower() and log["topics"]==[topic,"0x"+"0"*64,recipient] and receipt["status"]=="0x1":
                print("Chainlink CCIP-BnM confirmed:",txid,"minted raw units",int(log["data"],16),flush=True)
                sys.exit(0)
        sys.exit("Chainlink transaction did not show the expected mint")
    time.sleep(4)
sys.exit("Chainlink receipt pending")
