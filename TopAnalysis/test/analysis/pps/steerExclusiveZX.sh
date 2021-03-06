#!/bin/bash

WHAT=$1; 
if [ "$#" -ne 1 ]; then 
    echo "steerExclusiveZX.sh <SEL/MERGE/PLOT/WWW>";
    echo "   SEL           - launches selection jobs to the batch, output will contain summary trees and control plots"; 
    echo "   MERGESEL        - merge output"
    echo "   PLOTSEL         - make plots"
    echo "   TRAINPUDISCR    - train pileup discriminator"
    echo "   RUNPRED         - run pileup discriminator prediction"
    echo "   PREPAREMIX      - prepare bank of events for event mixing from the summary trees"
    echo "   COLLECTMIX      - collects all the mixing events found in PREPAREANA"
    echo "   ANA/ANASIG      - run analysis on the summary trees"
    echo "   CHECKANA        - check analysis integrity and re-run locally jobs which have failed"
    echo "   PLOTANA         - plot analysis results"
    echo "   OPTIMSTATANA    - optimize the statistical analysis"
    echo "   FINALIZESTATANA - define the final datacards based on the results of the optimization"
    echo "   WWW             - move plots to web-based area"
    exit 1; 
fi

#to run locally use local as queue + can add "--njobs 8" to use 8 parallel jobs
queue=tomorrow

githash=2017_unblind_multi

datadir=/store/cmst3/group/top/RunIIReReco/2017/f439f08_ul
datajson=${CMSSW_BASE}/src/TopLJets2015/TopAnalysis/test/analysis/pps/datasamples.json
RPout_json=$CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/golden_noRP.json

mcdir=/store/cmst3/group/top/RunIIReReco/ab05162
mcjson=${CMSSW_BASE}/src/TopLJets2015/TopAnalysis/test/analysis/pps/mcsamples.json
zxjson=$CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/zx_samples.json
genweights=genweights_ab05162.root

signaldir=/store/cmst3/group/top/RunIIReReco/2017/vxsimulations_7Dec
signaljson=$CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/signal_samples.json

outdir=/store/cmst3/user/psilva/ExclusiveAna/final/${githash}
anadir=${outdir}/analysis_0p035
wwwdir=/eos/user/p/psilva/www/ExclusiveAna_${githash}

plot_signal_json=$CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/plot_signal_samples.json
plot_signal_ext_json=$CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/plot_signal_samples_ext.json


zbias_samples_json=$CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/zbias_samples.json



lumi=41529
ppsLumi=37193
lptalumi=2642
lptappslumi=2288
lumiUnc=0.025


RED='\e[31m'
NC='\e[0m'
case $WHAT in

    TESTSEL )

        #inputfileTag=MC13TeV_2017_GJets_HT400to600
        #inputfileTESTSEL=${mcdir}/${inputfileTag}/Chunk_0_ext0.root
        
        inputfileTag=Data13TeV_2017B_SinglePhoton
        inputfileTESTSEL=${datadir}/${inputfileTag}/Chunk_0_ext0.root

        python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/scripts/runLocalAnalysis.py \
            -i ${inputfileTESTSEL} --tag ${inputfileTag} \
            -o testsel.root --genWeights ${genweights} \
            --njobs 1 -q local --debug \
            --era era2017 -m ExclusiveZX::RunExclusiveZX --ch 0 --runSysts;
        ;;

    SEL )
        baseCmd="$CMSSW_BASE/src/TopLJets2015/TopAnalysis/scripts/runLocalAnalysis.py"
        baseCmd="${baseCmd} --genWeights ${genweights} --era era2017 -m ExclusiveZX::RunExclusiveZX --ch 0 --runSysts"
        baseCmd="${baseCmd} -o ${outdir} -q ${queue}"
        
	python ${baseCmd} --farmappendix ZXData -i ${datadir} --only ${datajson};
	python ${baseCmd} --farmappendix ZXMC   -i ${mcdir}   --only ${mcjson},${zxjson};
	;;

    CHECKSELINTEG )
        python scripts/checkLocalAnalysisInteg.py ../../../FARM${githash}ZXMC/   analysis/data tree
        python scripts/checkLocalAnalysisInteg.py ../../../FARM${githash}ZXData/ analysis/data tree
        ;;

    MERGESEL )
	mergeOutputs.py /eos/cms/${outdir} True;
	;;

    PLOTSEL )
        lumiSpecs="--lumiSpecs a:${lptalumi}"
        kFactorList="--procSF #gamma+jets:1.4"        
	commonOpts="-i /eos/cms/${outdir} --puNormSF puwgtctr -l ${lumi} --mcUnc ${lumiUnc} ${kFactorList} ${lumiSpecs}"

	python scripts/plotter.py ${commonOpts} -j ${mcjson},${datajson}    -O /eos/cms/${outdir}/plots/sel -o plotter.root --only mll,pt,eta,met,jets,nvtx,ratevsrun --saveLog; 
        python scripts/plotter.py ${commonOpts} -j ${samples_json}    --rawYields --silent --only gen -O /eos/cms/${outdir}/plots/ -o plots/bkg_gen_plotter.root; 
	python scripts/plotter.py ${commonOpts} -j ${zx_samples_json} --rawYields --silent --only gen -O /eos/cms/${outdir}/plots/ -o plots/zx_gen_plotter.root;
        #python test/analysis/pps/computeDileptonSelEfficiency.py /eos/cms/${outdir}/plots/       
	;;

    TESTPREPAREMIX )
        predin=/eos/cms/${outdir}/Chunks
        file=Data13TeV_2017D_DoubleMuon_2.root
        predout=/eos/cms/${anadir}/mixing
        mkdir -p $predout
        
        #run locally
        python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/runExclusiveAnalysis.py --step 0 --jobs 1 \
            --json ${mcjson},${datajson},${signaljson} --RPout ${RPout_json} -o ${predout} -i ${predin} --only ${file} --maxEvents 10000
        ;;

    PREPAREMIX )       
        step=0
        predin=/eos/cms/${outdir}/Chunks
        predout=/eos/cms/${anadir}/mixing
        condor_prep=runana_condor.sub
        echo "executable  = ${CMSSW_BASE}/src/TopLJets2015/TopAnalysis/test/analysis/pps/wrapAnalysis.sh" > $condor_prep
        echo "output      = ${condor_prep}.out" >> $condor_prep
        echo "error       = ${condor_prep}.err" >> $condor_prep
        echo "log         = ${condor_prep}.log" >> $condor_prep
        echo "arguments   = ${CMSSW_BASE} ${step} ${predout} ${predin} \$(chunk)" >> $condor_prep
        echo "queue chunk matching (${predin}/Data*.root)" >> $condor_prep
        condor_submit $condor_prep
        
        #python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/runExclusiveAnalysis.py --step 0 --jobs 8 \
        #    --json ${samples_json} --RPout ${RPout_json} -o ${predout} -i ${predin};

        ;;

    CHECKMIX )
        python test/analysis/pps/checkFinalNtupleInteg.py /eos/cms/${outdir}/Chunks /eos/cms/${anadir}/mixing/Chunks 1 0
        ;;

    COLLECTMIX )
        python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/collectEventsForMixing.py /eos/cms/${anadir}
        ;;

    TESTANA )        
        predin=/eos/cms/${outdir}/Chunks
        file=Data13TeV_2017D_DoubleEG_2.root
        predin=/eos/cms/${signaldir}
        file=Z_m_X_1200_xangle_120_2017_preTS2.root
        mix_file=/eos/cms/${anadir}/mixing/mixbank.pck

        predout=./mixtest
        addOpt=""
        python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/runExclusiveAnalysis.py --step 1 --jobs 1 \
            --json ${mcjson},${datajson},${signaljson} --RPout ${RPout_json} -o ${predout} --mix ${mix_file} -i ${predin} --only ${file} ${addOpt};

        #predout=./mix1200
        #addOpt="--mixSignal /eos/cms/${anadir}/Z_m_X_1200_xangle_{0}_2017_preTS2_opt_v1_simu_reco.root"
        #python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/runExclusiveAnalysis.py --step 1 --jobs 1 \
        #    --json ${mcjson},${datajson},${signaljson} --RPout ${RPout_json} -o ${predout} --mix ${mix_file} -i ${predin} --only ${file} ${addOpt};
        ;;


    ANA )
        step=1
        predin=/eos/cms/${outdir}/Chunks
        predout=/eos/cms/${anadir}
        condor_prep=runana_condor.sub
        mix_file=/eos/cms/${anadir}/mixing/mixbank.pck
        echo "executable  = ${CMSSW_BASE}/src/TopLJets2015/TopAnalysis/test/analysis/pps/wrapAnalysis.sh" > $condor_prep
        echo "output       = ${condor_prep}.out" >> $condor_prep
        echo "error        = ${condor_prep}.err" >> $condor_prep
        echo "log          = ${condor_prep}.log" >> $condor_prep
        echo "+JobFlavour = \"tomorrow\"">> $condor_prep
        echo "request_cpus = 4" >> $condor_prep
        echo "arguments    = ${CMSSW_BASE} ${step} ${predout} ${predin} \$(chunk) ${mix_file}" >> $condor_prep
        echo "queue chunk matching (${predin}/*.root)" >> $condor_prep
        condor_submit $condor_prep

        #run locally
        #python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/runExclusiveAnalysis.py --step 1 --jobs 8 \
        #    --json ${mcjson},${datajson},${signaljson} --RPout ${RPout_json} -o ${predout} --mix ${mix_file} -i ${predin};
        
        ;;

    CHECKANA )
        #0-just check
        #1-run locally
        #2-submit to condor
        python test/analysis/pps/checkFinalNtupleInteg.py /eos/cms/${outdir}/Chunks /eos/cms/${anadir}/Chunks 2 1 /eos/cms/${anadir}/mixing/mixbank.pck
        ;;
    
    ANASIG )
        step=1
        predin=/eos/cms/${signaldir}
        predout=/eos/cms/${anadir}
        condor_prep=runanasig_condor.sub
        mix_file=/eos/cms/${anadir}/mixing/mixbank.pck
        echo "executable  = ${CMSSW_BASE}/src/TopLJets2015/TopAnalysis/test/analysis/pps/wrapAnalysis.sh" > $condor_prep
        echo "output      = ${condor_prep}.out" >> $condor_prep
        echo "error       = ${condor_prep}.err" >> $condor_prep
        echo "log         = ${condor_prep}.log" >> $condor_prep
        echo "+JobFlavour = \"tomorrow\"">> $condor_prep
        echo "request_cpus = 4" >> $condor_prep
        echo "arguments   = ${CMSSW_BASE} ${step} ${predout} ${predin} \$(chunk)" ${mix_file} >> $condor_prep
        echo "queue chunk matching (${predin}/*.root)" >> $condor_prep
        condor_submit $condor_prep

        #run locally
        #python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/analysis/pps/runExclusiveAnalysis.py --step 1 --jobs 8 \
        #    --json ${signaljson} --RPout ${RPout_json} --mix /eos/cms/${outdir}/mixing/mixbank.pck \
        #    -i /eos/cms/${signal_dir} -o anasig/;
        # cp -v anasig/Chunks/*.root /eos/cms/${outdir}/analysis/
        ;;
   
    CHECKANASIG )
        python test/analysis/pps/checkFinalNtupleInteg.py /eos/cms/${signaldir} /eos/cms/${anadir}/Chunks 1 1 /eos/cms/${anadir}/mixing/mixbank.pck
        ;;

    MERGEANA )
        mergeOutputs.py /eos/cms/${anadir};
        ;;

    BKGVALIDATION )       
        for pt in 0 40 60; do
            output=/eos/cms/${outdir}/bkg_ptll${pt}
            python test/analysis/pps/doBackgroundValidation.py \
                --doPerAngle -i /eos/cms/${anadir} \
                -o ${output} \
                --selCuts "bosonpt>=${pt} && l1pt>30 && l2pt>20" &
        done
        ;;

    PLOTANA )

        lumiSpecs="mmrpin:${ppsLumi},eerpin:${ppsLumi},emrpin:${ppsLumi},a:${lptalumi},arpin:${lptappslumi},arpinhpur:${lptappslumi}"   
        for c in neg pos hpur hpurpos hpurneg hpur120xangle hpur130xangle hpur140xangle hpur150xangle; do
            lumiSpecs="${lumiSpecs},mmrpin${c}:${ppsLumi},eerpin${c}:${ppsLumi},emrpin${c}:${ppsLumi},arpin${c}:${lptappslumi}";
        done
	baseOpts="-i /eos/cms/${anadir} --lumiSpecs ${lumiSpecs} --procSF #gamma+jets:1.4 -l ${lumi} --mcUnc ${lumiUnc} ${lumiSpecs} ${kFactorList}"
        commonOpts="${baseOpts} -j ${mcjson},${datajson} --signalJson ${plot_signal_ext_json} -O /eos/cms/${anadir}/plots"

        plots=xangle_arpinhpur xangle_eerpinhpur,xangle_mmrpinhpur,xangle_emrpinhpur,xangle_arpinhpur
        python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/scripts/plotter.py ${commonOpts} --only ${plots} --strictOnly --saveTeX --rebin 4;

        commonOpts="${baseOpts} -j ${mcjson},${datajson} --signalJson ${plot_signal_json} -O /eos/cms/${anadir}/plots"
        cats=(
            "" 
            "rpin"
            "rpinpos" "rpinneg"
            "rpinhpur" 
            "rpinhpurneg" "rpinhpurpos" 
            "rpinhpur120xangle" "rpinhpur130xangle" "rpinhpur140xangle" "rpinhpur150xangle" 
        )
        channels=(mm) #mm ee a em)
        for ch in ${channels[@]}; do #mm ee a em; do
           plots=""

            for c in "${cats[@]}"; do            
                evcat=${ch}${c}
                
                for p in ptll mll nvtx rho xangle mll mll_full yll etall ptll ptll_high l1eta l1pt l2eta l2pt acopl costhetacs met njets mpf zjb zj2b nch; do                  
                    plots="${p}_${evcat},${plots}"
                done

                if [[ $evcat == *"rpin"* ]]; then
                    for p in nextramu extramupt extramueta mmass ppcount ypp2d ypp mpp pzpp mpp2d mmass_full; do
                        plots="${p}_${evcat},${plots}"
                    done
                fi
                
                if [[ $evcat == *"pos"* || $evcat == *"neg"* ]]; then
                    for p in ntk csi csi2d; do
                        plots="${p}_${evcat},${plots}"
                    done
                fi            
            done

            if [[ $c == *"a"* ]]; then
                commonOpts="${commonOpts} --normToData"
            fi

            python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/scripts/plotter.py \
                ${commonOpts} --only ${plots} \
                --strictOnly  -o plotter_${ch}.root --saveLog &
        done
        
        ;;

    PLOTSIGACC )
        for m in 600 800 1200 1400; do 
            for i in `seq 2 5`; do 
                python test/analysis/pps/drawSignalPeak.py \
                    /eos/cms/${anadir}/Z_m_X_${m}_xangle_1${i}0_2017_preTS2.root ; 
            done 
        done
        mkdir -p /eos/cms/${anadir}/plots_signal
        mv mmass*sig* /eos/cms/${anadir}/plots_signal
        ;;


    PLOTLOCALSENS )       
        odir=/eos/cms/${anadir}/localsens
        mkdir -p ${odir};
        for xangle in 120 130 140 150; do
            python test/analysis/pps/estimateLocalSensitivity.py --xangle ${xangle} \
                -i /eos/cms/${anadir} -o ${odir} &            
        done
        ;;


    TESTSTATANA)

        echo "Generating a datacard takes a bit as it'll project the shapes for a given set of cuts"
        echo "You can run locally with python test/analysis/pps/generatedBinnedWorkspace.py and your preferred set of cuts"
        echo "Running with the default values for ${anadir} and output @ ppvx_analysis/test"
        commonOpts="-i /eos/cms/${anadir} --massList 800,1200,1600"
        python test/analysis/pps/generateBinnedWorkspace.py ${commonOpts} -o ppvx_${githash}/test &
        python test/analysis/pps/generateBinnedWorkspace.py ${commonOpts} -o ppvx_${githash}_signed/test --signed &

        ;;

    OPTIMSTATANA )
        
        #afs needs to be used here...
        python test/analysis/pps/prepareOptimScanCards.py -o ppvx_${githash}        -i /eos/cms/${anadir}
        python test/analysis/pps/prepareOptimScanCards.py -o ppvx_${githash}_signed -i /eos/cms/${anadir} --signed
        
        ;;

    INJECTSIGNAL )

        #afs needs to be used here...
        mu=0.5
        for m in 600 800 1200 1400; do
            python test/analysis/pps/prepareOptimScanCards.py -o ppvx_${githash}_${m}_${mu}         -i /eos/cms/${anadir} --injectMass ${m} --injectMu ${mu} --just 2,10,46;
            python test/analysis/pps/prepareOptimScanCards.py -o ppvx_${githash}_signed_${m}_${mu}  -i /eos/cms/${anadir} --injectMass ${m} --injectMu ${mu} --just 2,10,46 --signed;
        done

        ;;

    UNBLIND )

        #the real thing
        python test/analysis/pps/prepareOptimScanCards.py -o ppvx_${githash}_obs        --unblind  -i /eos/cms/${anadir} --just 2,10,46;
        python test/analysis/pps/prepareOptimScanCards.py -o ppvx_${githash}_signed_obs --unblind  -i /eos/cms/${anadir}  --just 2,10,46 --signed;
        

        ;;


    FINALIZESTATANA )
        for d in ppvx_${githash} ppvx_${githash}_signed; do
            python test/analysis/pps/compareOptimResults.py ${d}
            mkdir -p ${d}/plots
            mkdir -p /eos/cms/${anadir}/${d}
            mv *.{png,pdf,dat} /eos/cms/${anadir}/${d}
            mv limits*root  /eos/cms/${anadir}/${d}
        done
        ;;


    WWW )

	#cp $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/index.php ${wwwdir}
	#mkdir -p ${wwwdir}/presel
	#cp /eos/cms/${outdir}/plots/*.{png,pdf,dat} ${wwwdir}/presel
	#cp /eos/cms/${outdir}/plots/sel/*.{png,pdf,dat} ${wwwdir}/presel
	#cp $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/index.php ${wwwdir}/presel

        #analysis control plots
        #mkdir -p ${wwwdir}/ana
        #cp /eos/cms/${anadir}/plots/*.{png,pdf,dat} ${wwwdir}/ana
        #cp $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/index.php ${wwwdir}/ana

        #signal acceptance plots
        #mkdir -p ${wwwdir}/signal
        #cp /eos/cms/${anadir}/plots_signal/*.{png,pdf,dat} ${wwwdir}/signal
        #cp $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/index.php ${wwwdir}/signal

        #local sensitivity
        #mkdir -p ${wwwdir}/localsens
        cp /eos/cms/${anadir}/localsens/*.{png,pdf,dat} ${wwwdir}/localsens
        cp $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/index.php ${wwwdir}/localsens

        #background closure plots
        for pt in 0 40 60; do
            pdir=/eos/cms/${outdir}/bkg_ptll${pt}
            odir=${wwwdir}/bkg/emu_ptll${pt}
            mkdir -p ${odir}
            cp ${pdir}/*.{png,pdf,dat} ${odir}
            cp $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/index.php ${odir}
        done

        #statistical analysis
        for d in ppvx_${githash} ppvx_${githash}_signed; do
            odir=${wwwdir}/stat/${d}
            mkdir -p ${odir}
            #cp /eos/cms/${anadir}/${d}/* ${odir}
            #cp /eos/cms/${anadir}/${d}/limits* ${odir}
            #cp $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/index.php ${odir}
        done
        #cp $CMSSW_BASE/src/TopLJets2015/TopAnalysis/test/index.php ${wwwdir}/stat

        ;;


    EXTRA )
        
        scriptDir=test/analysis/pps
        echo ""
        echo "This is a printout of additional scripts used for cross checks or specific plots"
        echo "Scripts can be found in ${scriptDir}"
        echo "[Additional supporting plots]"
        echo "python test/analysis/pps/compareNvtx.py"
        echo ""
        echo "[Display fit shapes]"
        echo "python ${scriptDir}/showFitShapes.py ppvx_${githash}/optim_1 1200 z"
        echo ""
        echo "[Signal injection studies]"
        esStr=""
        for m in 600 800 1200 1400; do
            resStr="${resStr} PPgX:${m}:ppvx_${githash}_${m}_0.5/optim_2 PPzX:${m}:ppvx_${githash}_${m}_0.5/optim_10"
        done
        odir=${wwwdir}/stat/ppvx_${githash}
        echo "python ${scriptDir}/drawPvalCurve.py ${resStr}"
        echo "mv *.{png,pdf} ${odir}"
        echo "mv limits*root ${odir}"
        odir=${odir}_signed
        resStr=${resStr//${githash}/${githash}_signed}
        echo "python ${scriptDir}/drawPvalCurve.py ${resStr}"
        echo "mv *.{png,pdf} ${odir}"
        echo "mv limits*root ${odir}"
        echo ""
        echo "[High pT version]"
        odir=${wwwdir}/stat/ppvx_${githash}/highpt
        echo "python ${scriptDir}/drawPvalCurve.py PPzX:0:ppvx_${githash}/optim_46"
        echo "mkdir -p ${odir}"
        echo "mv *.{png,pdf} ${odir}"
        echo "mv limits*root ${odir}"
        echo ""
        echo "[Limit comparison]"
        odir=${wwwdir}/stat/ppvx_${githash}
        echo "python ${scriptDir}/compareLimits.py 'baseline':${odir}/limits_PPzX_1200.root 'high p_{T}':${odir}/highpt/limits_PPzX_0.root '#eta signed':${odir}_signed/limits_PPzX_1200.root"
        echo "mv limitcomp* ${odir}"
        echo ""
        ;;
    

    ###                                                                                         ###
    ### THESE OPTIONS WERE USED AT SOME POINT IN THE ANALYSIS BUT HAVE NOT BEEN TESTED RECENTLY ###
    ###                                                                                         ###

    TESTSYNCH )
        
        python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/scripts/runLocalAnalysis.py \
            -i /store/cmst3/user/psilva/ExclusiveAna/synch/Data13TeV_2017_DoubleMuon_synch.root \
            -o testsynch.root --genWeights ${genweights} \
            --njobs 1 -q local --debug \
            --era era2017 -m ExclusiveZX::RunExclusiveZX --ch 0 --runSysts;

        ;;



    TRAINPUDISCR )
        echo "Please remember to use a >10_3_X release for this step"

        commonOpts="--trainFrac 0.3  --RPout ${RPout_json} -o /eos/cms/${outdir}/train_results"
        python test/analysis/pps/trainPUdiscriminators.py ${commonOpts} -s "isZ && evcat==13*13 && bosonpt<10 && trainCat>=0" 
        #python test/analysis/pps/trainPUdiscriminators.py ${commonOpts} -s "hasZBTrigger && trainCat>=0" --zeroBiasTrain

        ;;

    RUNPRED )
        predin=/eos/cms/${outdir}/Chunks
        predout=/eos/cms/${outdir}/Chunks/pudiscr 
        condor_prep=runpred_condor.sub
        echo "executable  = ${CMSSW_BASE}/src/TopLJets2015/TopAnalysis/test/analysis/pps/wrapPUDiscrTrain.sh" > $condor_prep
        echo "output      = ${condor_prep}.out" >> $condor_prep
        echo "error       = ${condor_prep}.err" >> $condor_prep
        echo "log         = ${condor_prep}.log" >> $condor_prep
        echo "requirements = (OpSysAndVer =?= \"SLCern6\")"  >> $condor_prep
        echo "arguments   = ${predout} \$(chunk)" >> $condor_prep
        echo "queue chunk matching (${predin}/*.root)" >> $condor_prep
        condor_submit $condor_prep
        ;;

    PLOTANAPERERA )

        plots=""
        for evcat in a ee mm em; do
            for p in ptll mll; do 
                plots="${p}_${evcat},${plots}"
            done
        done        
        for era in B C D E F; do
            alumi=${lptalumi}
            eralumi=${lumi}
            if [ "${era}" = "B" ]; then
                alumi=`echo ${alumi}*0.115 | bc`
                eralumi=`echo ${eralumi}*0.115 | bc`
            elif [ "${era}" = "C" ]; then
                alumi=`echo ${alumi}*0.233 | bc`
                eralumi=`echo ${eralumi}*0.233 | bc`
            elif [ "${era}" = "D" ]; then
                alumi=`echo ${alumi}*0.103 | bc`
                eralumi=`echo ${eralumi}*0.103 | bc`
            elif [ "${era}" = "E" ]; then
                alumi=`echo ${alumi}*0.22 | bc`
                eralumi=`echo ${eralumi}*0.22 | bc`
            elif [ "${era}" = "F" ]; then
                alumi=`echo ${alumi}*0.329 | bc`
                eralumi=`echo ${eralumi}*0.329 | bc`
            fi

	    baseOpts="-i /eos/cms/${anadir} --lumiSpecs a:${alumi} --procSF #gamma+jets:1.4 -l ${eralumi} --mcUnc ${lumiUnc}"
            era_json=test/analysis/pps/test_samples_${era}.json;
            commonOpts="${baseOpts} -j ${era_json} --signalJson ${plot_signal_json} -O /eos/cms/${anadir}/plots${era}"
            python $CMSSW_BASE/src/TopLJets2015/TopAnalysis/scripts/plotter.py ${commonOpts} --only ${plots} --strictOnly;
        done
        ;;







esac
