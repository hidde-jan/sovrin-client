import json
import logging
import re

import pytest
from plenum.common.constants import PUBKEY

from anoncreds.protocol.types import SchemaKey, ID
from sovrin_client.test import waits
from sovrin_client.test.agent.faber import create_faber, bootstrap_faber

from sovrin_common.roles import Roles
from stp_core.loop.eventually import eventually
from sovrin_client.test.agent.test_walleted_agent import TestWalletedAgent
from sovrin_common.roles import Roles
from sovrin_client.agent.walleted_agent import WalletedAgent
from sovrin_client.agent.runnable_agent import RunnableAgent
from sovrin_common.setup_util import Setup
from sovrin_common.constants import ENDPOINT

from sovrin_client.test.agent.acme import create_acme, bootstrap_acme
from sovrin_client.test.agent.helper import buildFaberWallet, buildAcmeWallet, \
    buildThriftWallet
from sovrin_client.test.agent.thrift import create_thrift, bootstrap_thrift
from sovrin_client.test.cli.conftest import faberMap, acmeMap, \
    thriftMap
from sovrin_client.test.cli.helper import newCLI
from sovrin_client.test.cli.test_tutorial import syncInvite, acceptInvitation, \
    aliceRequestedTranscriptClaim, jobApplicationProofSent, \
    jobCertClaimRequested, bankBasicProofSent, bankKYCProofSent, \
    setPromptAndKeyring

concerningLogLevels = [logging.WARNING,
                       logging.ERROR,
                       logging.CRITICAL]

whitelist = ["is not connected - message will not be sent immediately.If this problem does not resolve itself - check your firewall settings"]

class TestWalletedAgent(WalletedAgent, RunnableAgent):
    pass

def getSeqNoFromCliOutput(cli):
    seqPat = re.compile("Sequence number is ([0-9]+)")
    m = seqPat.search(cli.lastCmdOutput)
    assert m
    seqNo, = m.groups()
    return seqNo


@pytest.fixture(scope="module")
def newGuyCLI(looper, tdir, tconf):
    # FIXME: rework logic of setup because Setup.setupAll does not exist anymore
    # Setup(tdir).setupAll()
    return newCLI(looper, tdir, subDirectory='newguy', conf=tconf)


@pytest.mark.skip("SOV-569. Not yet implemented")
def testGettingStartedTutorialAgainstSandbox(newGuyCLI, be, do):
    be(newGuyCLI)
    do('connect test', within=3, expect="Connected to test")
    # TODO finish the entire set of steps


@pytest.mark.skipif('sys.platform == "win32"', reason='SOV-384')
def testManual(do, be, poolNodesStarted, poolTxnStewardData, philCLI,
               connectedToTest, nymAddedOut, attrAddedOut,
               aliceCLI, newKeyringOut, aliceMap,
               tdir, syncLinkOutWithEndpoint, jobCertificateClaimMap,
               syncedInviteAcceptedOutWithoutClaims, transcriptClaimMap,
               reqClaimOut, reqClaimOut1, susanCLI, susanMap):
    eventually.slowFactor = 3

    # Create steward and add nyms and endpoint attributes of all agents
    _, stewardSeed = poolTxnStewardData
    be(philCLI)
    do('new keyring Steward', expect=['New keyring Steward created',
                                      'Active keyring set to "Steward"'])

    mapper = {'seed': stewardSeed.decode()}
    do('new key with seed {seed}', expect=['Key created in keyring Steward'],
       mapper=mapper)
    do('connect test', within=3, expect=connectedToTest)

    # Add nym and endpoint for Faber, Acme and Thrift
    agentIpAddress = "127.0.0.1"
    faberAgentPort = 5555
    acmeAgentPort = 6666
    thriftAgentPort = 7777
    faberEndpoint = "{}:{}".format(agentIpAddress, faberAgentPort)
    acmeEndpoint = "{}:{}".format(agentIpAddress, acmeAgentPort)
    thriftEndpoint = "{}:{}".format(agentIpAddress, thriftAgentPort)

    faberHa = "{}:{}".format(agentIpAddress, faberAgentPort)
    acmeHa = "{}:{}".format(agentIpAddress, acmeAgentPort)
    thriftHa = "{}:{}".format(agentIpAddress, thriftAgentPort)
    faberId = 'FuN98eH2eZybECWkofW6A9BKJxxnTatBCopfUiNxo6ZB'
    acmeId = '7YD5NKn3P4wVJLesAmA1rr7sLPqW9mR1nhFdKD518k21'
    thriftId = '9jegUr9vAMqoqQQUEAiCBYNQDnUbTktQY9nNspxfasZW'
    faberPk = '5hmMA64DDQz5NzGJNVtRzNwpkZxktNQds21q3Wxxa62z'
    acmePk = 'C5eqjU7NMVMGGfGfx2ubvX5H9X346bQt5qeziVAo3naQ'
    thriftPk = 'AGBjYvyM3SFnoiDGAEzkSLHvqyzVkXeMZfKDvdpEsC2x'
    for nym, ha, pk in [(faberId, faberHa, faberPk),
                    (acmeId, acmeHa, acmePk),
                    (thriftId, thriftHa, thriftPk)]:
        m = {'remote': nym, 'endpoint': json.dumps({ENDPOINT:
                                                    {'ha': ha, PUBKEY: pk}})}
        do('send NYM dest={{remote}} role={role}'.format(role=Roles.TRUST_ANCHOR.name),
            within=5,
            expect=nymAddedOut, mapper=m)
        do('send ATTRIB dest={remote} raw={endpoint}', within=5,
           expect=attrAddedOut, mapper=m)

    # Start Faber Agent and Acme Agent

    fMap = faberMap(agentIpAddress, faberAgentPort)
    aMap = acmeMap(agentIpAddress, acmeAgentPort)
    tMap = thriftMap(agentIpAddress, thriftAgentPort)

    agentParams = [
        (create_faber, "Faber College", faberAgentPort,
         buildFaberWallet, bootstrap_faber),
        (create_acme, "Acme Corp", acmeAgentPort,
         buildAcmeWallet, bootstrap_acme),
        (create_thrift, "Thrift Bank", thriftAgentPort,
         buildThriftWallet, bootstrap_thrift)
    ]

    for create_agent_fuc, agentName, agentPort, buildAgentWalletFunc, bootstrap_func in agentParams:
        agent = create_agent_fuc(name=agentName, wallet=buildAgentWalletFunc(),
                                 base_dir_path=tdir, port=agentPort)
        RunnableAgent.run_agent(agent, bootstrap=bootstrap_func(agent), looper=philCLI.looper)

    for p in philCLI.looper.prodables:
        if p.name == 'Faber College':
            faberAgent = p
        if p.name == 'Acme Corp':
            acmeAgent = p
        if p.name == 'Thrift Bank':
            thriftAgent = p

    async def checkTranscriptWritten():
        faberId = faberAgent.wallet.defaultId
        schemaId = ID(SchemaKey("Transcript", "1.2", faberId))
        schema = await faberAgent.issuer.wallet.getSchema(schemaId)
        assert schema
        assert schema.seqId

        issuerPublicKey = await faberAgent.issuer.wallet.getPublicKey(schemaId)
        assert issuerPublicKey  # TODO isinstance(issuerPublicKey, PublicKey)

    async def checkJobCertWritten():
        acmeId = acmeAgent.wallet.defaultId
        schemaId = ID(SchemaKey("Job-Certificate", "0.2", acmeId))
        schema = await acmeAgent.issuer.wallet.getSchema(schemaId)
        assert schema
        assert schema.seqId

        issuerPublicKey = await acmeAgent.issuer.wallet.getPublicKey(schemaId)
        assert issuerPublicKey
        assert issuerPublicKey.seqId

    timeout = waits.expectedTranscriptWritten()
    philCLI.looper.run(eventually(checkTranscriptWritten, timeout=timeout))
    timeout = waits.expectedJobCertWritten()
    philCLI.looper.run(eventually(checkJobCertWritten, timeout=timeout))

    # Defining inner method for closures
    def executeGstFlow(name, userCLI, userMap, be, connectedToTest, do, fMap,
                       aMap, jobCertificateClaimMap, newKeyringOut, reqClaimOut,
                       reqClaimOut1, syncLinkOutWithEndpoint,
                       syncedInviteAcceptedOutWithoutClaims, tMap,
                       transcriptClaimMap):

        async def getPublicKey(wallet, schemaId):
            return await wallet.getPublicKey(schemaId)

        async def getClaim(schemaId):
            return await userCLI.agent.prover.wallet.getClaims(schemaId)

        # Start User cli

        be(userCLI)
        setPromptAndKeyring(do, name, newKeyringOut, userMap)
        do('connect test', within=3, expect=connectedToTest)
        # Accept faber
        do('load sample/faber-invitation.sovrin')
        syncInvite(be, do, userCLI, syncLinkOutWithEndpoint, fMap)
        do('show link faber')
        acceptInvitation(be, do, userCLI, fMap,
                         syncedInviteAcceptedOutWithoutClaims)
        # Request claim
        do('show claim Transcript')
        aliceRequestedTranscriptClaim(be, do, userCLI, transcriptClaimMap,
                                      reqClaimOut,
                                      None,  # Passing None since its not used
                                      None)  # Passing None since its not used

        faberSchemaId = ID(SchemaKey('Transcript', '1.2', fMap['remote']))
        faberIssuerPublicKey = userCLI.looper.run(
            getPublicKey(faberAgent.issuer.wallet, faberSchemaId))
        userFaberIssuerPublicKey = userCLI.looper.run(
            getPublicKey(userCLI.agent.prover.wallet, faberSchemaId))
        assert faberIssuerPublicKey == userFaberIssuerPublicKey

        do('show claim Transcript')
        assert userCLI.looper.run(getClaim(faberSchemaId))

        # Accept acme
        do('load sample/acme-job-application.sovrin')
        syncInvite(be, do, userCLI, syncLinkOutWithEndpoint, aMap)
        acceptInvitation(be, do, userCLI, aMap,
                         syncedInviteAcceptedOutWithoutClaims)
        # Send claim
        do('show claim request Job-Application')
        do('set first_name to Alice')
        do('set last_name to Garcia')
        do('set phone_number to 123-45-6789')
        do('show claim request Job-Application')
        # Passing some args as None since they are not used in the method
        jobApplicationProofSent(be, do, userCLI, aMap, None, None, None)
        do('show claim Job-Certificate')
        # Request new available claims Job-Certificate
        jobCertClaimRequested(be, do, userCLI, None,
                              jobCertificateClaimMap, reqClaimOut1, None)

        acmeSchemaId = ID(SchemaKey('Job-Certificate', '0.2', aMap['remote']))
        acmeIssuerPublicKey = userCLI.looper.run(getPublicKey(
            acmeAgent.issuer.wallet, acmeSchemaId))
        userAcmeIssuerPublicKey = userCLI.looper.run(getPublicKey(
            userCLI.agent.prover.wallet, acmeSchemaId))
        assert acmeIssuerPublicKey == userAcmeIssuerPublicKey

        do('show claim Job-Certificate')
        assert userCLI.looper.run(getClaim(acmeSchemaId))

        # Accept thrift
        do('load sample/thrift-loan-application.sovrin')
        acceptInvitation(be, do, userCLI, tMap,
                         syncedInviteAcceptedOutWithoutClaims)
        # Send proofs
        bankBasicProofSent(be, do, userCLI, tMap, None)

        thriftAcmeIssuerPublicKey = userCLI.looper.run(getPublicKey(
            thriftAgent.issuer.wallet, acmeSchemaId))
        assert acmeIssuerPublicKey == thriftAcmeIssuerPublicKey
        passed = False
        try:
            bankKYCProofSent(be, do, userCLI, tMap, None)
            passed = True
        except:
            thriftFaberIssuerPublicKey = userCLI.looper.run(getPublicKey(
                thriftAgent.issuer.wallet, faberSchemaId))
            assert faberIssuerPublicKey == thriftFaberIssuerPublicKey
        assert passed

    executeGstFlow("Alice", aliceCLI, aliceMap, be, connectedToTest, do, fMap,
                   aMap, jobCertificateClaimMap, newKeyringOut, reqClaimOut,
                   reqClaimOut1, syncLinkOutWithEndpoint,
                   syncedInviteAcceptedOutWithoutClaims, tMap,
                   transcriptClaimMap)

    aliceCLI.looper.runFor(3)

    # Same flow is executed by different cli
    # What is the purpose of this test? This should not work because its a different person
    # with different data or it is the same person but from a different state
    # executeGstFlow("Susan", susanCLI, susanMap, be, connectedToTest, do, fMap,
    #                aMap, jobCertificateClaimMap, newKeyringOut, reqClaimOut,
    #                reqClaimOut1, syncLinkOutWithEndpoint,
    #                syncedInviteAcceptedOutWithoutClaims, tMap,
    #                transcriptClaimMap)
