#!/usr/bin/env python

import ROOT
import copy
import optparse
import json
import sys
import os
import numpy
import array
import json
import random
import pickle
import array
import re
from collections import OrderedDict
from EventMixingTool import *
from TopLJets2015.TopAnalysis.HistoTool import *
from mixedEvent import *

VALIDLHCXANGLES=[120,130,140,150]
DIMUONS=13*13
EMU=11*13
DIELECTRONS=11*11
SINGLEPHOTON=22
MINCSI=0.035
MIXEDRP=None
MIXEDRPSIG=None # this is only for a test


def isValidRunLumi(run,lumi,runLumiList):

    """checks if run is available and lumi section was certified"""

    #no run/lumi to select, all is good by default
    if not runLumiList:
        return True

    #run is available
    if not run in runLumiList: 
        return True

    for lran in runLumiList[run]:
        if lumi>=lran[0] and lumi<=lran[1]:
            return False

    #reached this far, nothing found in list
    return True

def computeCosThetaStar(lm,lp):
    dil=lm+lp
    costhetaCS = 1./dil.M()
    if dil.Pz()<0 : costhetaCS *= -1
    costhetaCS *= (lm.E() + lm.Pz()) * (lp.E() - lp.Pz()) - (lm.E() - lm.Pz()) * (lp.E() + lp.Pz());
    costhetaCS /= ROOT.TMath.Sqrt( (dil.M())**2 + (dil.Pt())**2)
    return costhetaCS


def getTracksPerRomanPot(tree,mcTruth=False,usefarRP=True,minCsi=-1):

    """loops over the availabe tracks in the event and groups them by roman pot id"""

    tkPos=[]
    tkNeg=[]
    for itk in xrange(0,tree.nRPtk):
        rpid=tree.RPid[itk]
        try:
            csi=tree.RPfarcsi[itk] if usefarRP else tree.RPnearcsi[itk]
            if csi<minCsi: continue
        except:            
            if notMCTruth:
                csi=tree.RPfarx[itk] if useFarRP else tree.RPnearx[itk]
            else:
                csi=tree.RPtruecsi[itk] 

        if rpid==23  and csi>0: tkPos.append(csi)
        if rpid==123 and csi>0: tkNeg.append(csi)
        
    return (tkPos,tkNeg)

def buildDiProton(rptks,sqrts=13000.):

    """build a diproton system from to tracks in the arms of the roman pots"""

    if not rptks : return None
    if len(rptks[0])==0 or len(rptks[1])==0 : return None
    beamP=0.5*sqrts
    csiL,csiR=rptks[0][0],rptks[1][0]
    diproton=ROOT.TLorentzVector(0.,0.,beamP*(csiL-csiR),beamP*(csiL+csiR))
    return diproton


def buildMissingMassSystem(protons,boson,sqrts=13000.):
    """builds the system corresponding to the missing mass"""

    pp          = buildDiProton(protons,sqrts)
    mmassSystem = None
    if pp:
        inPP=ROOT.TLorentzVector(0,0,0,sqrts)
        mmassSystem=(pp-boson)
    return mmassSystem

def passHighPurSelection(protons,boson):
            
    """high purity selection for proton tracks"""
    
    highPur = True if protons and len(protons[0])==1 and len(protons[1])==1 else False  
    if highPur:
        if protons[0][0]<MINCSI or protons[0][0]>0.18 : highPur=False
        if protons[1][0]<MINCSI or protons[1][0]>0.18 : highPur=False

    return highPur


def getRandomEra():

    """generates a random era according to the integrated luminosity in each one"""

    r=random.random()
    if r<0.115   : return '2017B'
    elif r<0.348 : return '2017C'
    elif r<0.451 : return '2017D'
    elif r<0.671 : return '2017E'
    return '2017F'

def isSignalFile(inFile):
    isSignal=True if 'gamma_m_X_' in inFile or 'Z_m_X_' in inFile else False
    return isSignal

def isDYFile(inFile):
    isDY=True if 'DY50toInf' in inFile else False
    return isDY

def isPhotonSignalFile(inFile):
    isSignal=True if 'gamma_m_X_' in inFile else False
    return isSignal

def signalMassPoint(inFile):
    return float(os.path.basename(inFile).split('_')[3])

def isSignalFiducial(csiPos,csiNeg,gen_pzpp):

    if csiNeg<0.03 or csiPos<0.03 : return False
    if csiNeg>0.16 or csiPos>0.13 : return False
    return True

    #if gen_pzpp<-300: return False
    #if gen_pzpp>500 : return False
    #return True


def runExclusiveAnalysis(inFile,outFileName,runLumiList,effDir,maxEvents=-1):
    
    """event loop"""

    global MIXEDRP
    global MIXEDRPSIG

    isData=True if 'Data' in inFile else False
    isDY=isDYFile(inFile)
    isSignal=isSignalFile(inFile)
    isPhotonSignal=isPhotonSignalFile(inFile)
    gen_mX=signalMassPoint(inFile) if isSignal else 0.

    #bind main tree with pileup discrimination tree, if failed return
    tree=ROOT.TChain('analysis/data' if isSignal else 'tree')
    tree.AddFile(inFile)
    #try:
    #    pudiscr_tree=ROOT.TChain('pudiscr')
    #    baseName=os.path.basename(inFile)
    #    baseDir=os.path.dirname(inFile)
    #    pudiscr_file=os.path.join(baseDir,'pudiscr',baseName)
    #    if not os.path.isfile(pudiscr_file):
    #        raise ValueError(pudiscr_file+' does not exist')
    #    pudiscr_tree.AddFile(pudiscr_file)
    #    tree.AddFriend(pudiscr_tree)
    #    print 'Added pu tree for',inFile
    #except:
    #    #print 'Failed to add pu discrimination tree as friend for',inFile
    #    return


    #identify data-taking era
    era=None
    if isData:
        era=os.path.basename(inFile).split('_')[1]
    
    #check if it is signal and load     
    signalPt=[]
    mcEff={}
    if isSignal: 
        signalPt=[float(x) for x in re.findall(r'\d+', os.path.basename(inFile) )[2:]]
        for ch in ['eez','mmz','a']:
            effIn=ROOT.TFile.Open('%s/effsummary_%s_ptboson.root'%(effDir,ch))
            pname='gen%srec_ptboson_ZH#rightarrowllbb_eff'%ch
            if ch=='a': pname='genarec_ptboson_EWK #gammajj_eff'
            mcEff[ch]=effIn.Get(pname)
            effIn.Close()        

    #start event mixing tool
    evMixTool=EventMixingTool(mixedRP=MIXEDRP,validAngles=VALIDLHCXANGLES)
    
    #start histograms
    ht=HistoTool()   

    #main analysis histograms
    ht.add(ROOT.TH1F('nvtx',';Vertex multiplicity;Events',50,0,100))
    ht.add(ROOT.TH1F('rho',';Fastjet #rho;Events',50,0,50))
    ht.add(ROOT.TH1F('xangle',';LHC crossing angle [#murad];Events',4,120,160))
    ht.add(ROOT.TH1F('mll',';Invariant mass [GeV];Events',50,76,106))
    ht.add(ROOT.TH1F('mll_full',';Invariant mass [GeV];Events',50,0,250))
    ht.add(ROOT.TH1F('yll',';Rapidity;Events',50,-3,3))
    ht.add(ROOT.TH1F('etall',';Pseudo-rapidity;Events',50,-6,6))
    ht.add(ROOT.TH1F('ptll',';Transverse momentum [GeV];Events',50,0,250))
    ht.add(ROOT.TH1F('ptll_high',';Transverse momentum [GeV];Events',50,50,500))
    ht.add(ROOT.TH1F('l1eta',';Pseudo-rapidiy;Events',50,0,2.5))
    ht.add(ROOT.TH1F('l1pt',';Transverse momentum [GeV];Events',50,0,250))
    ht.add(ROOT.TH1F('l2eta',';Pseudo-rapidiy;Events',50,0,2.5))
    ht.add(ROOT.TH1F('l2pt',';Transverse momentum [GeV];Events',50,0,250))
    ht.add(ROOT.TH1F('acopl',';A=1-|#Delta#phi|/#pi;Events',50,0,1))
    ht.add(ROOT.TH1F('costhetacs',';cos#theta_{CS};Events',50,-1,1))

    #pileup control
    #ht.add(ROOT.TH1F('rfc',';Random forest classifier probability;Events',50,0,1))
    for d in ['HF','HE','EE','EB']:
        ht.add(ROOT.TH1F('PFMult'+d,';PF multiplicity (%s);Events'%d,50,0,1000))
        ht.add(ROOT.TH1F('PFHt'+d,';PF HT (%s) [GeV];Events'%d,50,0,1000))
        ht.add(ROOT.TH1F('PFPz'+d,';PF P_{z} (%s) [TeV];Events'%d,50,0,40))
    ht.add(ROOT.TH1F('met',';Missing transverse energy [GeV];Events',50,0,200))
    ht.add(ROOT.TH1F('mpf',';MPF;Events',50,-5,5))
    ht.add(ROOT.TH1F('metbits',';MET filters;Events',124,0,124))
    ht.add(ROOT.TH1F('njets',';Jet multiplicity;Events',5,0,5))
    ht.add(ROOT.TH1F('zjb',';Z-jet balance [GeV];Events',50,-150,150))
    ht.add(ROOT.TH1F('zj2b',';Z-2 jets balance [GeV];Events',50,-150,150))
    ht.add(ROOT.TH1F('nch', ';Charged particle multiplicity;Events',50,0,50))
    ht.add(ROOT.TH1F('nextramu',';Additional muons ;Events',10,0,10))
    ht.add(ROOT.TH1F('extramupt',';Additional muon p_{T} [GeV] ;Events',10,0,50))
    ht.add(ROOT.TH1F('extramueta',';Additional muon pseudo-rapidty ;Events',10,0,2.5))

    #RP control
    ht.add(ROOT.TH1F('mpp',';Di-proton invariant mass [GeV];Events',50,0,3000))
    ht.add(ROOT.TH1F('pzpp',';Di-proton p_{z} [GeV];Events',50,-750,750))
    ht.add(ROOT.TH1F('ypp',';Di-proton rapidity;Events',50,-2.5,2.5))
    ht.add(ROOT.TH2F('mpp2d',';Far di-proton invariant mass [GeV];Near di-proton invariant mass [GeV];Events',50,0,3000,50,0,3000))
    ht.add(ROOT.TH2F('ypp2d',';Far di-proton rapidity;Near di-proton rapidity;Events',50,-3,3,50,-3,3))
    ht.add(ROOT.TH1F('mmass_full',';Missing mass [GeV];Events',50,-1000,3000))
    ht.add(ROOT.TH1F('mmass',';Missing mass [GeV];Events',50,0,3000))
    ht.add(ROOT.TH1F('ntk',';Track multiplicity;Events',5,0,5))
    ht.add(ROOT.TH1F('ppcount',';pp candidates;Events',3,0,3))
    ht.add(ROOT.TH1F('csi',';#xi;Events',50,0,0.3))
    ht.add(ROOT.TH2F('csi2d',';#xi(far);#xi(near);Events',50,0,0.3,50,0,0.3))
        
    nEntries=tree.GetEntries()              
    print '....analysing',nEntries,'in',inFile,', with output @',outFileName
    if maxEvents>0:
        nEntries=min(maxEvents,nEntries)
        print '      will process',nEntries,'events'

    #compute number of events weighted by target pz spectrum
    nSignalWgtSum=0.
    if isSignal:
        print 'Checking how many events are in the fiducial RP area...'
        for i in xrange(0,nEntries):
            tree.GetEntry(i)
            nSignalWgtSum += ROOT.TMath.Gaus(tree.gen_pzpp,0,0.391*gen_mX+624)
        print '...signal weight sum set to',nSignalWgtSum,' from ',nEntries,'raw events'


    #loop over events
    rpData={}
    selEvents=[]
    summaryVars='cat:wgt:xangle:'
    summaryVars+='l1pt:l1eta:l2pt:l2eta:acopl:bosonpt:bosoneta:bosony:costhetacs:njets:mpf:zjb:zj2b:'
    summaryVars+='nch:nvtx:rho:PFMultSumHF:PFHtSumHF:PFPzSumHF:rfc:gen_pzpp:gen_pzwgtUp:gen_pzwgtDown:'
    if isSignal: summaryVars+='gencsi1:gencsi2:'
    for pfix in ['','syst']:
        summaryVars+='{0}csi1:{0}csi2:{0}nearcsi1:{0}nearcsi2:{0}mpp:{0}ypp:{0}pzpp:{0}mmiss:'.format(pfix)
    summaryVars += 'mmissvup:mmissvdn:mixType:'
    summaryVars=summaryVars.split(':')[0:-1] #cut away last token
    nfail=[0,0,0]
    for i in xrange(0,nEntries):

        tree.GetEntry(i)

        if i%1000==0 : sys.stdout.write('\r [ %d/100 ] done' %(int(float(100.*i)/float(nEntries))))

        if isSignal:
            if isPhotonSignal and tree.evcat!=SINGLEPHOTON : continue
            if not isPhotonSignal and tree.evcat==SINGLEPHOTON : continue


        #base event selection
        if tree.evcat==DIELECTRONS and tree.isZ: 
            evcat='ee'
        elif tree.evcat==EMU       and not tree.isSS: 
            evcat='em'
        elif tree.evcat==DIMUONS   and tree.isZ: 
            evcat='mm'
        elif tree.evcat==SINGLEPHOTON and (isPhotonSignal or tree.hasATrigger) :         
            evcat="a" 
        elif tree.evcat==0 and tree.hasZBTrigger : 
            evcat=='zbias'
        else : 
            nfail[0]+=1
            continue

        #assign data-taking era and crossing angle
        evEra = era
        beamXangle = tree.beamXangle        
        if not isData:
            evEra=getRandomEra()            
            if not isSignal: 
                xbin=evMixTool.getRandomLHCCrossingAngle(evEra=evEra,
                                                         evCat=SINGLEPHOTON if tree.isA else DIMUONS)
                beamXangle=VALIDLHCXANGLES[xbin]

        #check if RP is in (MC assume true by default)
        isRPIn=False if isData else True
        if isData and beamXangle in VALIDLHCXANGLES and isValidRunLumi(tree.run,tree.lumi,runLumiList):
            isRPIn=True
        if not isRPIn : nfail[1]+=1

        #lepton kinematics
        l1p4=ROOT.TLorentzVector(0,0,0,0)
        l2p4=ROOT.TLorentzVector(0,0,0,0)   
        costhetacs=0
        acopl=0
        if tree.evcat!=SINGLEPHOTON and tree.evcat!=0:
            acopl=1.0-abs(ROOT.TVector2.Phi_mpi_pi(tree.l1phi-tree.l2phi))/ROOT.TMath.Pi()
            l1p4.SetPtEtaPhiM(tree.l1pt,tree.l1eta,tree.l1phi,tree.ml1)
            l2p4.SetPtEtaPhiM(tree.l2pt,tree.l2eta,tree.l2phi,tree.ml2)
            costhetacs=computeCosThetaStar(l1p4,l2p4)
            
            #at this point order by pT
            if l1p4.Pt()<l2p4.Pt(): 
                l1p4,l2p4=l2p4,l1p4

        #boson kinematics
        boson=ROOT.TLorentzVector(0,0,0,0)
        boson.SetPtEtaPhiM(tree.bosonpt,tree.bosoneta,tree.bosonphi,tree.mboson)
        isZ=tree.isZ
        isA=tree.isA
       
        #for the signal-electron hypothesis this cut needs to be applied
        hasEEEBTransition=False
        if isZ:
            if abs(l1p4.Eta())>1.4442 and abs(l1p4.Eta())<1.5660 : hasEEEBTransition=True
            if abs(l2p4.Eta())>1.4442 and abs(l2p4.Eta())<1.5660 : hasEEEBTransition=True

        #PU-related variables
        #for signal most of these will be overriden by mixing       
        n_extra_mu,nvtx,nch,rho,met,njets,PFMultSumHF,PFHtSumHF,PFPzSumHF,rfc=0,0,0,0,0,0,0,0,0,0
        mpf,zjb,zj2b=0,0,0
        extra_muons=[]
        if not isSignal:
            nvtx=tree.nvtx
            nch=tree.nchPV
            rho=tree.rho
            met=tree.met_pt
            metphi=tree.met_phi
            njets=tree.nj 
            PFMultSumHF=tree.PFMultSumHF
            PFHtSumHF=tree.PFHtSumHF
            PFPzSumHF=tree.PFPzSumHF
            #rfc=getattr(tree,'rfc_%d'%beamXangle)
            for im in range(tree.nrawmu):
                mup4=ROOT.TLorentzVector(0,0,0,0)
                mup4.SetPtEtaPhiM(tree.rawmu_pt[im],tree.rawmu_eta[im]/10.,tree.rawmu_phi[im]/10.,0.105)
                if mup4.DeltaR(l1p4)<0.05 : continue
                if mup4.DeltaR(l2p4)<0.05 : continue
                extra_muons.append( ROOT.TLorentzVector(mup4) )
            n_extra_mu=len(extra_muons)
            
            metp4=ROOT.TLorentzVector(0,0,0,0)
            metp4.SetPtEtaPhiM(met,0,metphi,0)
            mpf=1.+(metp4.Px()*boson.Px()+metp4.Py()*boson.Py())/(boson.Pt()**2+1.0e-6)            
            if njets>0: 
                zjb=tree.j1pt-boson.Pt()
                if njets>1:
                    j1p4=ROOT.TLorentzVector(0,0,0,0)
                    j1p4.SetPtEtaPhiM(tree.j1pt,tree.j1eta,tree.j1phi,tree.j1m)
                    j2p4=ROOT.TLorentzVector(0,0,0,0)
                    j2p4.SetPtEtaPhiM(tree.j2pt,tree.j2eta,tree.j2phi,tree.j2m)
                    zj2b=(j1p4+j2p4).Pt()-boson.Pt()

        #proton tracks (standard and mixed)
        far_rptks, near_rptks = [[],[]],[[],[]]
        if isSignal or (isData and isRPIn): 
            far_rptks  = getTracksPerRomanPot(tree,minCsi=MINCSI)
            near_rptks = getTracksPerRomanPot(tree,False,False)            

        #if data and there is nothing to mix store the main characteristics of the event and continue
        if evMixTool.isIdle():
            if isData and isRPIn:

                #for Z->mm use 25% otherwise we have way too many events to do this efficiently
                if (isZ and tree.evcat==DIMUONS and boson.Pt()<10 and random.random()<0.25) or evcat=='em':

                    rpDataKey=(evEra,beamXangle,int(tree.evcat))
                    if not rpDataKey in rpData: rpData[rpDataKey]=[]
                    rpData[rpDataKey].append( MixedEvent(beamXangle,
                                                         [len(extra_muons),nvtx,rho,PFMultSumHF,PFHtSumHF,PFPzSumHF,rfc],
                                                         far_rptks,
                                                         near_rptks
                                                    ) )
            continue

        #event mixing
        mixed_far_rptks,mixed_near_rptks,mixed_pudiscr=evMixTool.getNew(evEra=evEra,
                                                                        beamXangle=beamXangle,
                                                                        isData=isData,
                                                                        validAngles=VALIDLHCXANGLES,
                                                                        mixEvCategs=[DIMUONS,EMU])

        if isSignal:
            mixed_far_rptks,mixed_near_rptks=evMixTool.mergeWithMixedEvent(far_rptks,mixed_far_rptks,near_rptks,mixed_near_rptks)
            n_extra_mu,nvtx,rho,PFMultSumHF,PFHtSumHF,PFPzSumHF,rfc=mixed_pudiscr[DIMUONS]

        #kinematics using RP tracks
        far_protons     = far_rptks  if isData else mixed_far_rptks[DIMUONS]
        near_protons    = near_rptks if isData else mixed_near_rptks[DIMUONS]        
        highPur         = passHighPurSelection(far_protons,boson)
        ppSystem        = buildDiProton(far_protons)
        mmassSystem     = buildMissingMassSystem(far_protons,boson)
        nearppSystem    = buildDiProton(near_protons)
        nearmmassSystem = buildMissingMassSystem(near_protons,boson)

        #event categories
        cats=[]            
        cats.append(evcat)
        if isRPIn:
            cats += [evcat+'rpin']
            if highPur:
                cats += [evcat+'rpinhpur']
                if mmassSystem and mmassSystem.M()>0:
                    cats += [evcat+'rpinhpur%dxangle'%beamXangle]

        #fill control plots (for signal correct wgt by ee efficiency curve and duplicate for mm channel)
        wgt=tree.evwgt
        finalPlots=[[wgt,cats]]        
        gen_pzpp=0
        gen_pzwgt=[1.,1.,1.]
        gen_csiPos,gen_csiNeg=0,0
        if isSignal:
            true_rptks=getTracksPerRomanPot(tree,True)

            if len(true_rptks[0])>0 : gen_csiPos=true_rptks[0][0]
            if len(true_rptks[1])>0 : gen_csiNeg=true_rptks[1][0]
            
            gen_pzpp=tree.gen_pzpp
            pzwid=0.391*gen_mX+624
            gen_pzwgt[0]=ROOT.TMath.Gaus(gen_pzpp,0,pzwid)
            gen_pzwgt[1]=ROOT.TMath.Gaus(gen_pzpp,0,pzwid*1.1)/gen_pzwgt[0]
            gen_pzwgt[2]=ROOT.TMath.Gaus(gen_pzpp,0,pzwid*0.9)/gen_pzwgt[0]

            #use the sum of pz weighted events as normalization factor
            if isZ:
                finalPlots=[ [wgt*gen_pzwgt[0]*mcEff['eez'].Eval(boson.Pt())/nSignalWgtSum , cats],
                             [wgt*gen_pzwgt[0]*mcEff['mmz'].Eval(boson.Pt())/nSignalWgtSum, [c.replace(evcat,'mm') for c in cats if c[0:2]=='ee']] ]

                #reject Z->ee if one electron in the transition
                if hasEEEBTransition:
                    finalPlots[0][0]=0.

            elif isPhotonSignal:
                finalPlots=[ [wgt*gen_pzwgt[0]*mcEff['a'].Eval(boson.Pt())/nSignalWgtSum, cats] ]

        for pwgt,pcats in finalPlots:   

            #fill plots only with fiducial signal contribution
            if isSignal and not isSignalFiducial(gen_csiPos,gen_csiNeg,tree.gen_pzpp): continue

            #boson kinematics
            ht.fill((l1p4.Pt(),pwgt),             'l1pt',         pcats)
            ht.fill((l2p4.Pt(),pwgt),             'l2pt',         pcats)
            ht.fill((abs(l1p4.Eta()),pwgt),       'l1eta',        pcats)
            ht.fill((abs(l2p4.Eta()),pwgt),       'l2eta',        pcats)
            ht.fill((acopl,pwgt),                 'acopl',        pcats)
            ht.fill((boson.M(),pwgt),             'mll',          pcats)
            ht.fill((boson.M(),pwgt),             'mll_full',     pcats)
            ht.fill((boson.Rapidity(),pwgt),      'yll',          pcats)
            ht.fill((boson.Eta(),pwgt),           'etall',        pcats)
            ht.fill((boson.Pt(),pwgt),            'ptll',         pcats)
            ht.fill((boson.Pt(),pwgt),            'ptll_high',    pcats)
            ht.fill((costhetacs,pwgt),            'costhetacs',   pcats)
            
            #pileup related
            ht.fill((beamXangle,pwgt),            'xangle', pcats)
            ht.fill((nvtx,pwgt),                  'nvtx',   pcats)
            ht.fill((rho,pwgt),                   'rho',    pcats)
            ht.fill((met,pwgt),                   'met',    pcats)
            ht.fill((mpf,pwgt),                   'mpf',    pcats)
            ht.fill((njets,pwgt),                 'njets',  pcats)
            if njets>0: ht.fill((zjb,pwgt),       'zjb',    pcats)
            if njets>1: ht.fill((zj2b,pwgt),      'zj2b',   pcats)
            ht.fill((nch,pwgt),                   'nch',    pcats) 
            #ht.fill((getattr(tree,'rfc_%d'%beamXangle),pwgt), 'rfc',         pcats)
            ht.fill((PFMultSumHF,pwgt),     'PFMultHF',    pcats)
            ht.fill((PFHtSumHF,pwgt),       'PFHtHF',      pcats)
            ht.fill((PFPzSumHF/1.e3,pwgt),  'PFPZHF',      pcats)
            ht.fill((n_extra_mu,pwgt), 'nextramu', pcats)
            if not isSignal:
                ht.fill((tree.metfilters,pwgt), 'metbits', pcats)
                for sd in ['HE','EE','EB']:
                    ht.fill((getattr(tree,'PFMultSum'+sd),pwgt),    'PFMult'+sd, pcats)
                    ht.fill((getattr(tree,'PFHtSum'+sd),pwgt),      'PFHt'+sd,   pcats)
                    ht.fill((getattr(tree,'PFPzSum'+sd)/1.e3,pwgt), 'PFPZ'+sd,   pcats)
                for mp4 in extra_muons:
                    ht.fill((mp4.Pt(),pwgt), 'extramupt', pcats)
                    ht.fill((abs(mp4.Eta()),pwgt), 'extramueta', pcats)

            #proton counting and kinematics
            if far_protons and len(far_protons)>0:
                for irp,rpside in [(0,'pos'),(1,'neg')]:
                    ht.fill((len(far_protons[irp]),pwgt), 'ntk',    pcats,rpside)
                    for csi in far_protons[irp]:
                        ht.fill((csi,pwgt), 'csi', pcats,rpside)                        
                        if not near_protons : continue
                        if len(near_protons[irp])==0 : continue
                        csi_near=near_protons[irp][0]
                        ht.fill((csi,csi_near,pwgt), 'csi2d', pcats,rpside)

            #diproton kinematics
            if not ppSystem:
                ht.fill((0,pwgt), 'ppcount', pcats)
            else:
                ht.fill((1,pwgt),                   'ppcount',   pcats)
                ht.fill((ppSystem.M(),pwgt),        'mpp',       pcats)
                ht.fill((ppSystem.Pz(),pwgt),       'pzpp',       pcats)
                ht.fill((ppSystem.Rapidity(),pwgt), 'ypp',       pcats)                                
                if nearppSystem:
                    ht.fill((2,pwgt),                                                     'ppcount', pcats)
                    ht.fill((ppSystem.M(),nearppSystem.M(),pwgt),                         'mpp2d',   pcats)
                    ht.fill((ppSystem.Rapidity(),nearppSystem.Rapidity(),pwgt), 'ypp2d',   pcats)
                    
                mmass=mmassSystem.M()
                ht.fill((mmass,pwgt), 'mmass_full',     pcats)
                if mmass>0:
                    ht.fill((mmass,pwgt), 'mmass',     pcats)                    

            #signal characteristics in the absense of pileup
            if isSignal:
                nopu_far_protons  = far_rptks
                nopu_near_protons = near_rptks
                nopu_ppSystem     = buildDiProton(nopu_far_protons)
                if nopu_ppSystem:
                    nopu_mmassSystem = buildMissingMassSystem(nopu_far_protons,boson)
                    nopu_mmass       = nopu_mmassSystem.M()
                    ht.fill((nopu_ppSystem.M(),pwgt),  'mpp',         pcats, 'nopu')
                    ht.fill((nopu_mmass,pwgt),         'mmass_full',  pcats, 'nopu')
                    if nopu_mmass>0:
                        ht.fill((nopu_mmass,pwgt), 'mmass',  pcats, 'nopu')

        if not isData and not isSignal and not isDY : continue
        
        #save the event summary for the statistical analysis        
        nMixTries=100 if isData else 1
        for itry in range(2*nMixTries+1):

            itry_wgt=wgt

            #nominal 
            if itry==0:
                mixType           = 0 
                far_protons       = far_rptks
                near_protons      = near_rptks

                #shift csi by 1%
                far_protons_syst=[]
                near_protons_syst=[]
                for iside in range(2):

                    if far_protons:
                        far_protons_syst.append( [1.01*x for x in far_protons[iside] ] )
                    else:
                        far_protons_syst.append([])

                    if near_protons:
                        near_protons_syst.append( [1.01*x for x in near_protons[iside] ] )
                    else:
                        near_protons_syst.append([])

            else:
                
                #get a new event to mix
                mixed_far_rptks,mixed_near_rptks,_ = evMixTool.getNew(evEra=evEra,
                                                                      beamXangle=beamXangle,
                                                                      isData=isData,
                                                                      validAngles=VALIDLHCXANGLES,
                                                                      mixEvCategs=[DIMUONS,EMU])

                if MIXEDRPSIG:
                    sigCsi=random.choice( MIXEDRPSIG[beamXangle] )
                    for mixEvCat in mixed_far_rptks:
                        tksPos=mixed_far_rptks[mixEvCat][0]+[sigCsi[0]]
                        shuffle(tksPos)
                        tksNeg=mixed_far_rptks[mixEvCat][1]+[sigCsi[1]]
                        shuffle(tksNeg)
                        mixed_far_rptks[mixEvCat]=(tksPos,tksNeg)

                #merge signal protons with pileup protons for first attempt
                if isSignal and itry==1:
                    mixed_far_rptks,mixed_near_rptks=evMixTool.mergeWithMixedEvent(far_rptks,mixed_far_rptks,
                                                                                   near_rptks,mixed_near_rptks)
                    n_extra_mu,nvtx,rho,PFMultSumHF,PFHtSumHF,PFPzSumHF,rfc=mixed_pudiscr[DIMUONS]

                itry_wgt = wgt/float(nMixTries)

                if itry<=nMixTries or isSignal:
                    mixType           = 1
                    if isSignal: mixType=itry
                    far_protons       = mixed_far_rptks[DIMUONS]
                    far_protons_syst  = mixed_far_rptks[EMU]
                    near_protons      = mixed_near_rptks[DIMUONS]
                    near_protons_syst = mixed_near_rptks[EMU]
                else:
                    mixType           = 2
                    far_protons       = [mixed_far_rptks[DIMUONS][0],far_rptks[1]]
                    far_protons_syst  = [far_rptks[0],mixed_far_rptks[DIMUONS][1]]
                    near_protons      = [mixed_near_rptks[DIMUONS][0],near_rptks[1]]
                    near_protons_syst = [near_rptks[0],mixed_near_rptks[DIMUONS][1]]

            evSummary=[tree.evcat,itry_wgt,beamXangle,
                       l1p4.Pt(),l1p4.Eta(),l2p4.Pt(),l2p4.Eta(),acopl,boson.Pt(),boson.Eta(),boson.Rapidity(),costhetacs,
                       njets,mpf,zjb,zj2b,
                       nch,nvtx,rho,PFMultSumHF,PFHtSumHF,PFPzSumHF,rfc,gen_pzpp,gen_pzwgt[1],gen_pzwgt[2]]

            if isSignal: evSummary += [gen_csiPos,gen_csiNeg]


            passAtLeastOneSelection=False

            #check if nominal passes the selection and and info to the event
            highPur     = passHighPurSelection(far_protons,boson)
            ppSystem    = buildDiProton(far_protons)
            mmassSystem = buildMissingMassSystem(far_protons,boson)            
            
            #vary boson energy scale
            boson_up=boson*1.03
            mmassSystem_vup = buildMissingMassSystem(far_protons,boson_up)            
            boson_dn=boson*0.97
            mmassSystem_vdn = buildMissingMassSystem(far_protons,boson_dn)            
            
            if highPur and mmassSystem:
                passAtLeastOneSelection=True
                near_csiL=near_protons[0][0] if len(near_protons[0]) else 0
                near_csiR=near_protons[1][0] if len(near_protons[1]) else 0
                evSummary+=[far_protons[0][0],far_protons[1][0],near_csiL,near_csiR,
                            ppSystem.M(),ppSystem.Rapidity(),ppSystem.Pz(),mmassSystem.M()]
            else:
                evSummary+=[0]*8

            #repeat for systematics
            highPur_syst     = passHighPurSelection(far_protons_syst,boson)
            ppSystem_syst    = buildDiProton(far_protons_syst)
            mmassSystem_syst = buildMissingMassSystem(far_protons_syst,boson)            
            
            if highPur_syst and mmassSystem_syst:
                passAtLeastOneSelection=True
                near_csiL=near_protons_syst[0][0] if len(near_protons_syst[0]) else 0
                near_csiR=near_protons_syst[1][0] if len(near_protons_syst[1]) else 0
                evSummary+=[far_protons_syst[0][0],far_protons_syst[1][0],near_csiL,near_csiR,
                            ppSystem_syst.M(),ppSystem_syst.Rapidity(),ppSystem_syst.Pz(),mmassSystem_syst.M()]
            else:
                evSummary+=[0]*8
            
            #add information on the type of event (non-mix/mixed)
            evSummary += [ mmassSystem_vup.M() if mmassSystem_vup else 0.,
                           mmassSystem_vdn.M() if mmassSystem_vdn else 0.,
                           mixType]

            #if no selection passes the cuts ignore its summary
            if not passAtLeastOneSelection: continue

            #for signal update the event weight for ee/mm/photon hypothesis
            if isData or isDY:
                selEvents.append(evSummary)
            elif isSignal:
                if isZ:
                    #add a copy for ee
                    if not hasEEEBTransition:
                        eeEvSummary=copy.copy(evSummary)
                        eeEvSummary[0]=DIELECTRONS
                        eeEvSummary[1]=evSummary[1]*gen_pzwgt[0]*mcEff['eez'].Eval(boson.Pt())/nSignalWgtSum
                        selEvents.append(eeEvSummary)                    
                
                    #add a copy for mm
                    mmEvSummary=copy.copy(evSummary)
                    mmEvSummary[0]=DIMUONS
                    mmEvSummary[1]=evSummary[1]*gen_pzwgt[0]*mcEff['mmz'].Eval(boson.Pt())/nSignalWgtSum
                    selEvents.append(mmEvSummary)
                
                if isA:
                    #add a copy for the photon
                    aEvSummary=copy.copy(evSummary)
                    aEvSummary[0]=SINGLEPHOTON
                    aEvSummary[1]=evSummary[1]*gen_pzwgt[0]*mcEff['a'].Eval(boson.Pt())/nSignalWgtSum
                    selEvents.append(aEvSummary)

    #dump events for the mixing
    nSelRPData=sum([len(rpData[x]) for x in rpData])
    if nSelRPData>0:
        rpDataOut=outFileName.replace('.root','.pck')                
        print 'Saving',nSelRPData,'events for mixing in',rpDataOut
        with open(rpDataOut,'w') as cachefile:
            pickle.dump(rpData,cachefile, pickle.HIGHEST_PROTOCOL)        

    #if there was no mixing don't do anything else
    if not MIXEDRP: return 

    #save results
    ht.writeToFile(outFileName)

    #dump events for fitting
    nSelEvents=len(selEvents)    
    if nSelEvents>0:
        print 'Adding',nSelEvents,'selected events to',outFileName,'(',nfail,'events failed baseline selection)'
        fOut=ROOT.TFile.Open(outFileName,'UPDATE')
        fOut.cd()
        t=ROOT.TNtuple('data','data',':'.join(summaryVars))
        for v in selEvents : 
            t.Fill(array.array("f",v))
        t.Write()
        fOut.Close()
 
def runExclusiveAnalysisPacked(args):

    """wrapper for parallel execution"""

    try:
        runExclusiveAnalysis(*args)
    except Exception as e:
        print 50*'<'
        print "  Problem with", args[1], "continuing without"
        print e
        print 50*'<'
        return False
    
def runAnalysisTasks(opt):

    """create analysis tasks"""

    #read samples to process
    task_dict={}    
    for jsonF in opt.json.split(','):
        with open(jsonF,'r') as cachefile:
            samples=json.load(cachefile,  encoding='utf-8', object_pairs_hook=OrderedDict).items()
            for x in samples:
                task_dict[x[0]]=[]

    #group chunks matching the same name
    for file_path in os.listdir(opt.input):
        
        if opt.only:
            if not file_path in opt.only: 
                continue

        file_name,ext=os.path.splitext(file_path)
        if ext != '.root' : continue
        
        #check if file tag is already in the list of samples to process
        if isSignalFile(file_name):
            tag=file_name
        else:
            lastTkn=file_name.rfind('_')
            tag=file_name[0:lastTkn]

        if not tag in task_dict: continue
        task_dict[tag].append( os.path.join(opt.input,file_path) )

    #parse json file with list of run/lumi sections
    with open(opt.RPout,'r') as cachefile:        
        runLumi=json.load(cachefile,  encoding='utf-8', object_pairs_hook=OrderedDict).items()
        runLumi={int(x[0]):x[1] for x in runLumi}

    #used to test inclusion of potential signal (test case from conveners request)
    global MIXEDRPSIG
    if opt.mixSignal:

        print 'Going to add mixed signal here from %s'%opt.mixSignal
        print 'Use this at your own risk...'

        MIXEDRPSIG={}
        for a in VALIDLHCXANGLES:
            MIXEDRPSIG[a]=[]
            fIn=ROOT.TFile.Open(opt.mixSignal.format(a))
            data=fIn.Get('data')
            for i in range(data.GetEntriesFast()):
                data.GetEntry(i)
                if data.mixType!=0 : continue
                MIXEDRPSIG[a].append( (data.csi1,data.csi2) )
            fIn.Close()
            print '\t',a,'murad has',len(MIXEDRPSIG[a]),'events'

    #open this just once as it's quite heavy
    global MIXEDRP
    if opt.mix:
        print 'Analysing mixfile',opt.mix
        with open(opt.mix,'r') as cachefile:
            MIXEDRP=pickle.load(cachefile)
        print 'Size of mixing bank is',sys.getsizeof(MIXEDRP),'byte'


    #create the tasks and submit them
    import multiprocessing as MP
    pool = MP.Pool(opt.jobs)
    task_list=[]
    for x in task_dict.keys():
        
        isData = True if 'Data' in x else False
        if opt.step==0 and not isData : continue
        runLumiList=runLumi if isData else None
        for f in task_dict[x]:
            fOut='%s/Chunks/%s'%(opt.output,os.path.basename(f))
            task_list.append( (f,fOut,runLumiList,opt.effDir,opt.maxEvents) )

    pool.map(runExclusiveAnalysisPacked,task_list)


def main():
    usage = 'usage: %prog [options]'
    parser = optparse.OptionParser(usage)
    parser.add_option('-i', '--input',
                      dest='input',   
                      default='/eos/cms/store/cmst3/user/psilva/ExclusiveAna/Chunks',
                      help='input directory with the files [default: %default]')
    parser.add_option('--jobs',
                      dest='jobs', 
                      default=8,
                      type=int,
                      help='# of jobs to process in parallel the trees [default: %default]')
    parser.add_option('--maxEvents',
                      dest='maxEvents', 
                      default=-1,
                      type=int,
                      help='# of events to process [default: %default]')
    parser.add_option('--json',
                      dest='json', 
                      default='pps_samples.json',
                      type='string',
                      help='json with the files to process')
    parser.add_option('--only',
                      dest='only', 
                      default=None,
                      type='string',
                      help='only this file (or CSV list of files)')
    parser.add_option('--RPout',
                      dest='RPout', 
                      default='golden_noRP.json',
                      type='string',
                      help='json with the runs/lumi sections in which RP are out')
    parser.add_option('--effDir',
                      dest='effDir', 
                      default='/eos/cms//store/cmst3/user/psilva/ExclusiveAna/final/ab05162/plots/',
                      type='string',
                      help='directory with efficiency files for signal weighting')
    parser.add_option('--step',
                      dest='step', 
                      default=0,
                      type=int,
                      help='analysis step: 0 - prepare event mixing bank; 1 - analysis')
    parser.add_option('--mix',
                      dest='mix',
                      default=None,
                      type='string',
                      help='bank of events to use for the mixing')
    parser.add_option('--mixSignal',
                      dest='mixSignal',
                      default=None,
                      type='string',
                      help='this is just for a test : what if signal protons are added on top of the pileup protons?')
    parser.add_option('-o', '--output',
                      dest='output', 
                      default='analysis',
                      help='Output directory [default: %default]')
    (opt, args) = parser.parse_args()
    
    #transform CSV to list
    if opt.only: opt.only=[os.path.basename(x) for x in opt.only.split(',')]

    os.system('mkdir -p %s/Chunks' % opt.output)
    runAnalysisTasks(opt)
        

if __name__ == "__main__":
    sys.exit(main())
