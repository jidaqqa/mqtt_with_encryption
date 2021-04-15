from enum import Enum


class PacketIdentifer(Enum):
    CONNECT = 1
    CONNACK = 2
    PUBLISH = 3
    PUBACK = 4
    PUBREC = 5
    PUBCOMP = 7
    SUBSCRIBE = 8
    SUBACK = 9
    UNSUBSCRIBE = 10
    UNSUBACK = 11
    PINGREQ = 12
    PINGRESP = 13
    DISCONNECT = 14
    AUTH = 15


class Status(Enum):
    FRESH = 0
    CONN_RECV = 1
    PUB_RECV = 2
    SUB_RECV = 3
    ERROR = 4
    DISCONNECTED = 5


class Properties(Enum):
    # CONNECT
    SessionExpiryInterval = 17
    ReceiveMaximum = 33
    MaximumPacketSize = 39
    TopicAliasMaximum = 34
    RequestResponseInformation = 25
    RequestProblemInformation = 23
    UserProperty = 38
    AuthenticationMethod = 21
    AuthenticationData = 22
    #PUBLISH
    PayloadFormatIndicator = 1
    MessageExpiryInterval = 2
    TopicAlias = 35
    ResponseTopic = 8
    CorrelationData = 9
    #SUBSCRIBE
    SubscriptionIdentifier = 11
    ReasonString = 31

    #UTILITY
    Version = 100


class ConnectReasonCodes(Enum):
    Success = 0x00
    UnspecifiedError = 0x80
    MalformedPacket = 0x81
    ProtocolError = 0x82
    ImplementationSpecificError = 0x83
    UnsupportedProtocolVersion = 0x84
    ClientIdentifierNotValid = 0x85
    BadUserNameOrPassword = 0x86
    NotAuthorized = 0x87
    ServerUnavailable = 0x88
    ServerBusy = 0x89
    Banned = 0x8A
    BadAuthenticationMethod = 0x8C
    TopicNameInvalid = 0x90
    PacketTooLarge = 0x95
    QuotaExceeded = 0x97
    PayloadFormatInvalid = 0x99
    RetainNotSupported = 0x9A
    QoSNotSupported = 0x9B
    UseAnotherServer = 0x9C
    ServerMoved = 0x9D
    ConnectionRateExceeded = 0x9F


class SubackReasonCodes(Enum):
    GrantedQOS0 = 0x00
    GrantedQOS1 = 0x01
    GrantedQOS2 = 0x02
    UnspecifiedError = 0x80
    ImplementationSpecificError = 0x83
    NotAuthorized = 0x87
    TopicFilterInvalid = 0x8F
    PacketIdentifierInUse = 0x91
    QuotaExceeded = 0x97
    SharedSubscriptionsNotSupported = 0x9E
    SubscriptionIdentifierNotSupported = 0xA1
    WildcardSubscriptionsNotSupported = 0xA2


class Version(Enum):
    MQTTv31 = 0x4
    MQTTv5 = 0x5
