""" Transactions are derived from Blocks txList.

To recreate (raw mongo, should be adapted for motor):
db.blocks.aggregate([ {$unwind: "$txList"}, {$replaceRoot: { newRoot: "$txList" }}, {$out: "transactions"}])
"""

import pymongo
from nulsexplorer.model.base import BaseClass, Index

import logging
import operator
LOGGER = logging.getLogger('model.transactions')

class Transaction(BaseClass):
    COLLECTION = "transactions"

    INDEXES = [Index("hash", unique=True),
               Index("blockHeight", pymongo.ASCENDING),
               Index("blockHeight", pymongo.DESCENDING),
               Index("time", pymongo.DESCENDING),
               Index("outputs.address"),
               Index("inputs.address")]

    @classmethod
    async def input_txdata(cls, tx_data, batch_mode=False,
                           batch_transactions=None):
        #await cls.collection.insert(tx_data)
        transaction = tx_data
        for i, inputdata in enumerate(transaction['inputs']):
            fhash = inputdata['fromHash']
            fidx = inputdata['fromIndex']
            source_tx = None
            if batch_mode and batch_transactions is not None:
                source_tx = batch_transactions.get(fhash, None)
                if source_tx is not None:
                    source_output = source_tx['outputs'][fidx]
                    source_output['status'] = 3
                    source_output['toHash'] = transaction['hash']
                    source_output['toIndex'] = i

            if source_tx is None:
                source_tx = await cls.collection.find_one_and_update(
                    dict(hash=fhash),
                    {'$set': {
                        ('outputs.%d.status' % fidx): 3,
                        ('outputs.%d.toHash' % fidx): transaction['hash'],
                        ('outputs.%d.toIndex' % fidx): i
                    }})

            if source_tx is not None:
                in_from = source_tx['outputs'][inputdata['fromIndex']]
                inputdata['address'] = in_from['address']
            #     in_from['status'] = 3
            #     in_from['toHash'] = transaction.hash
            #     in_from['toIndex'] = i
            #     await source_tx.save()

        for outputdata in transaction['outputs']:
            if 'status' not in outputdata:
                if outputdata.get("lockTime", -1) > -1:
                    outputdata['status'] = 2 # how to know between 1 and 2 ?
                else:
                    outputdata['status'] = 0
        if batch_mode:
            return transaction
        else:
            try:
                await cls.collection.insert_one(tx_data)
            except pymongo.errors.DuplicateKeyError:
                LOGGER.warning("Transaction %s was already there" % transaction['hash'])
