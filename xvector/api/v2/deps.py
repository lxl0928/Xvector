from __future__ import annotations

from xvector.services.alias import AliasService
from xvector.services.collection import CollectionService
from xvector.services.import_job import ImportService
from xvector.services.index import IndexService
from xvector.services.partition import PartitionService
from xvector.services.role import RoleService
from xvector.services.user import UserService
from xvector.services.vector import VectorService
from xvector.services.context import AppContext


class Services:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.user = UserService(ctx)
        self.role = RoleService(ctx)
        self.collection = CollectionService(ctx)
        self.partition = PartitionService(ctx)
        self.index = IndexService(ctx)
        self.alias = AliasService(ctx)
        self.vector = VectorService(ctx)
        self.import_job = ImportService(ctx)
