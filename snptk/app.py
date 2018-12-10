from os.path import join

import snptk.core
import snptk.util

from snptk.util import debug

def update_snpid_and_position(args):
    bim_fname = args['bim']
    dbsnp_fname = args['dbsnp']
    snp_history_fname = args['snp_history']
    rs_merge_fname = args['rs_merge']
    output_prefix = args['output_prefix']

    snp_history = snptk.core.execute_load(snptk.core.load_snp_history, snp_history_fname, merge_method='set')
    rs_merge = snptk.core.execute_load(snptk.core.load_rs_merge, rs_merge_fname, merge_method='update')

    #-----------------------------------------------------------------------------------
    # Build a list of tuples with the original snp_id and updated_snp_id
    #-----------------------------------------------------------------------------------
    snp_map = []

    for entry in snptk.core.load_bim(bim_fname):
        snp_id = entry['snp_id']
        snp_id_new = snptk.core.update_snp_id(snp_id, snp_history, rs_merge)
        snp_map.append((snp_id, entry['chromosome'] + ':' + entry['position'], snp_id_new))

    #-----------------------------------------------------------------------------------
    # Load dbsnp by snp_id
    #-----------------------------------------------------------------------------------
    dbsnp = snptk.core.execute_load(
        snptk.core.load_dbsnp_by_snp_id,
        dbsnp_fname,
        set([snp for pair in snp_map for snp in pair]),
        merge_method='update')

    #-----------------------------------------------------------------------------------
    # Generate edit instructions
    #-----------------------------------------------------------------------------------
    #delete, update, coord_update

    snps_to_delete, snps_to_update, coords_to_update, chromosomes_to_update = update_logic(snp_map, dbsnp)

    with open(join(output_prefix, 'deleted_snps.txt'), 'w') as f:
        for snp_id in snps_to_delete:
            print(snp_id, file=f)

    with open(join(output_prefix, 'updated_snps.txt'), 'w') as f:
        for snp_id, snp_id_new in snps_to_update:
            print(snp_id + '\t' + snp_id_new, file=f)

    with open(join(output_prefix, 'coord_update.txt'), 'w') as f:
        for snp_id, coord_new in coords_to_update:
            print(snp_id + '\t' + coord_new, file=f)

    with open(join(output_prefix, 'chr_update.txt'), 'w') as f:
        for snp_id, chromosome in chromosomes_to_update:
            print(snp_id + '\t' + chromosome, file=f)


def snpid_from_coord(args):
    debug(f'snpid_from_coord: {args}', 1)

    bim_fname = args['bim']
    dbsnp_fname = args['dbsnp']

    coordinates = set()

    bim_entries = snptk.core.load_bim(bim_fname)

    for entry in bim_entries:
        coordinates.add(entry['chromosome'] + ':' + entry['position'])

    db = snptk.core.execute_load(snptk.core.load_dbsnp_by_coordinate, dbsnp_fname, coordinates, merge_method='extend')

    for entry in bim_entries:
        k = entry['chromosome'] + ':' + entry['position']

        if k in db:
            if len(db[k]) > 1:
                debug(f'Has more than one snp_id db[{k}] = {str(db[k])}')
            else:
                if db[k][0] != entry['snp_id']:
                    debug(f'Rewrote snp_id {entry["snp_id"]} to {db[k][0]} for position {k}')
                    entry['snp_id'] = db[k][0]

        else:
            debug('NO_MATCH: ' + '\t'.join(entry.values()))

        print('\t'.join(entry.values()))


def update_logic(snp_map, dbsnp):

    snps_to_delete = []
    snps_to_update = []
    coords_to_update = []
    chromosomes_to_update = []

    for snp_id, original_coord, snp_id_new in snp_map:

        # If snp has not been deleted
        if snp_id_new:

            # If the snp has been updated (merged)
            if snp_id_new != snp_id:

                # If the merged snp was already in the original
                if snp_id_new in [snp[0] for snp in snp_map]:
                    snps_to_delete.append(snp_id)

                elif snp_id_new in dbsnp:
                    snps_to_update.append((snp_id, snp_id_new))
                    debug(f'original_coord={original_coord} updated_coord={dbsnp[snp_id_new]}')

                    new_chromosome, new_position = dbsnp[snp_id_new].split(':')
                    original_chromosome, original_position = original_coord.split(':')

                    if new_position != original_position:
                        coords_to_update.append((snp_id_new, new_position))

                    if new_chromosome != original_chromosome:
                        chromosomes_to_update.append((snp_id_new, new_chromosome))

                else:
                    snps_to_delete.append(snp_id)

            else:
                # If the snp has not been updaed (merge)
                if snp_id in dbsnp:
                    debug(f'original_coord={original_coord} updated_coord={dbsnp[snp_id]}')

                    new_chromosome, new_position = dbsnp[snp_id].split(':')
                    original_chromosome, original_position = original_coord.split(':')

                    if new_position != original_position:
                        coords_to_update.append((snp_id, new_position))

                    if new_chromosome != original_chromosome:
                        chromosomes_to_update.append((snp_id, new_chromosome))

        # If snp has been deleted
        else:
            snps_to_delete.append(snp_id)

    return snps_to_delete, snps_to_update, coords_to_update, chromosomes_to_update
