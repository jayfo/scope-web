import aws_infrastructure.tasks.ssh
import contextlib
import pymongo
import pymongo.database


def _documentdb_client(
    *,
    # If an SSH port forward is required, an ExitStack must also be provided
    context_manager: contextlib.ExitStack = None,
    # If an SSH port forward is required, provide an instance_ssh_config
    instance_ssh_config: aws_infrastructure.tasks.ssh.SSHConfig = None,
    # Connection information
    host: str,
    port: int,
    direct_connection: bool,
    tls_insecure: bool,
    user: str,
    password: str,
) -> pymongo.MongoClient:
    # Check if we are responsible for an SSH connection and a port forward
    if instance_ssh_config is not None:
        if context_manager is None:
            raise ValueError(
                "If instance_ssh_config is provided, then context_manager is required"
            )
        if not direct_connection:
            raise ValueError(
                "If instance_ssh_config is provided, then direct_connection must be True"
            )
        if not tls_insecure:
            raise ValueError(
                "If instance_ssh_config is provided, then tls_insecure must be True"
            )

    # Determine a host and port to connect, set up a port forward if necessary
    if instance_ssh_config is not None:
        # We are responsible for setting up an SSH connection and a port forward
        ssh_client = context_manager.enter_context(
            aws_infrastructure.tasks.ssh.SSHClientContextManager(
                ssh_config=instance_ssh_config
            )
        )
        port_forward = context_manager.enter_context(
            aws_infrastructure.tasks.ssh.SSHPortForwardContextManager(
                ssh_client=ssh_client,
                remote_host=host,
                remote_port=port,
            )
        )

        # Update host and port for forwarding
        host = "127.0.0.1"
        port = port_forward.local_port
    else:
        # We may or may not be invoked in the context of an existing port forward.
        # Rely on provided parameters.
        pass

    return pymongo.MongoClient(
        # Synchronously initiate the connection
        connect=True,
        # Connect via SSH port forward
        host=host,
        port=port,
        directConnection=direct_connection,
        # DocumentDB requires SSL, but port forwarding means the certificate will not match
        tls=True,
        tlsInsecure=tls_insecure,
        # Compress network traffic
        compressors="zstd",
        # PyMongo defaults to retryable writes, which are not supported by DocumentDB
        # https://docs.aws.amazon.com/documentdb/latest/developerguide/functional-differences.html#functional-differences.retryable-writes
        retryWrites=False,
        # Connect with provided account
        username=user,
        password=password,
    )


def documentdb_client_admin(
    *,
    # If an SSH port forward is required, an ExitStack must also be provided
    context_manager: contextlib.ExitStack = None,
    # If an SSH port forward is required, provide an instance_ssh_config
    instance_ssh_config: aws_infrastructure.tasks.ssh.SSHConfig = None,
    # Connection information
    host: str,
    port: int,
    direct_connection: bool,
    tls_insecure: bool,
    admin_user: str,
    admin_password: str,
) -> pymongo.MongoClient:
    """
    Obtain a DocumentDB client, authenticated as the cluster administrator.
    """
    return _documentdb_client(
        context_manager=context_manager,
        instance_ssh_config=instance_ssh_config,
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        direct_connection=direct_connection,
        tls_insecure=tls_insecure,
    )


def documentdb_client_database(
    *,
    # If an SSH port forward is required, an ExitStack must also be provided
    context_manager: contextlib.ExitStack = None,
    # If an SSH port forward is required, provide an instance_ssh_config
    instance_ssh_config: aws_infrastructure.tasks.ssh.SSHConfig = None,
    # Connection information
    host: str,
    port: int,
    direct_connection: bool,
    tls_insecure: bool,
    # Desired database
    database_name: str,
    user: str,
    password: str,
) -> pymongo.database.Database:
    """
    Obtain a DocumentDB client, authenticated as the user associated with a specific database.
    """

    client = _documentdb_client(
        context_manager=context_manager,
        instance_ssh_config=instance_ssh_config,
        host=host,
        port=port,
        user=user,
        password=password,
        direct_connection=direct_connection,
        tls_insecure=tls_insecure,
    )

    return client.get_database(database_name)
