"""
Entry-point for the archive subsystem, which leverages the object store subsystem. This provides a configuration and lookup
point.

This is primarily used for the analysis archive feature of the system, but is not specific to that usage.

"""
import time
from anchore_engine.clients.services.simplequeue import SimpleQueueClient
from anchore_engine.clients.services.catalog import CatalogClient
from anchore_engine.clients.services import internal_client_for
import anchore_engine.subsys.taskstate
from anchore_engine.subsys import logger


_manager_singleton = None


def initialize():
    """
    Initializes the object evacuator manager to hold queue of images.

    NOTE: this is not thread-safe, should be called once on service startup, not in request threads/path

    :return:
    """
    global _manager_singleton
    if _manager_singleton is None:
        try:
            _manager_singleton = GracefulEvacuator()
        except Exception as ex:
            logger.exception('OLEKSII Error initializing archive manager')
    else:
        logger.warn('OLEKSII evacuator already initialized, skipping redundant init')


class GracefulEvacuator(object):

    def __init__(self):
        self.__shutdown_queue = []

    def evacuate(self):
        if len(self.__shutdown_queue) > 0:
            q_client = internal_client_for(SimpleQueueClient, userId=None)
            for qobj in self.__shutdown_queue:
                image_record = qobj.get('data')
                if not q_client.is_inqueue('images_to_analyze', qobj):
                    logger.error(
                        f"OLEKSII_QUEUE_EVACUATE {qobj.get('data', {}).get('imageDigest')} has pushed back local qsize: {len(self.__shutdown_queue)}"
                    )
                    imageDigest = image_record.get("imageDigest")
                    catalog_client = internal_client_for(CatalogClient, userId=image_record.get('userId'))

                    try:
                        image = catalog_client.get_image(imageDigest)
                        if not image_record:
                            raise Exception("empty image record from catalog")
                    except Exception as err:
                        logger.warn("dequeued image cannot be fetched from catalog - skipping evacuation (" + str(
                            imageDigest) + ") - exception: " + str(err))
                        return (True)

                    if image['analysis_status'] != anchore_engine.subsys.taskstate.complete_state('analyze'):
                        image['analysis_status'] = anchore_engine.subsys.taskstate.base_state('analyze')
                        if imageDigest:
                            catalog_client.update_image(imageDigest, image)
                            q_client.enqueue('images_to_analyze', image_record)

    def add(self, qobj):
        if qobj not in self.__shutdown_queue:
            self.__shutdown_queue.append(qobj)
            logger.error(
                f"OLEKSII_QUEUE_ADD {qobj.get('data', {}).get('imageDigest')} has added qsize: {len(self.__shutdown_queue)} - {self}"
            )

    def delete(self, qobj):
        self.__shutdown_queue.remove(qobj)
        logger.error(
            f"OLEKSII_QUEUE_DELETE {qobj.get('data', {}).get('imageDigest')} has been removed qsize: {len(self.__shutdown_queue)} - {self}"
        )


def get_manager() -> GracefulEvacuator:
    """
    Returns the object evacuator manager for the subsys
    :return:
    """
    global _manager_singleton
    if _manager_singleton is None:
        raise Exception('Not initialized. Call initialize')
    return _manager_singleton
